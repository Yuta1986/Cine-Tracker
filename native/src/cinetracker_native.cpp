#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include <ceres/ceres.h>
#include <ceres/product_manifold.h>
#include <ceres/rotation.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

namespace py = pybind11;

namespace {

struct PriorIndexResidual {
  PriorIndexResidual(int index, double mean, double sigma)
      : index_(index), mean_(mean), inv_sigma_(sigma > 0.0 ? 1.0 / sigma : 0.0) {}

  template <typename T>
  bool operator()(const T* const p, T* residual) const {
    residual[0] = T(inv_sigma_) * (p[index_] - T(mean_));
    return true;
  }

 private:
  int index_;
  double mean_;
  double inv_sigma_;
};

struct PlumbLineResidual {
  PlumbLineResidual(double u_d,
                    double v_d,
                    double fx,
                    double fy,
                    double cx,
                    double cy,
                    double a,
                    double b,
                    double c,
                    double sqrt_lambda)
      : u_d_(u_d),
        v_d_(v_d),
        fx_(fx),
        fy_(fy),
        cx_(cx),
        cy_(cy),
        a_(a),
        b_(b),
        c_(c),
        sqrt_lambda_(sqrt_lambda) {}

  template <typename T>
  bool operator()(const T* const k, T* residual) const {
    const T k1 = k[0];
    const T k2 = k[1];

    // distorted pixel -> normalized
    const T x_d = (T(u_d_) - T(cx_)) / T(fx_);
    const T y_d = (T(v_d_) - T(cy_)) / T(fy_);

    // inverse distortion via fixed-point iterations
    T x = x_d;
    T y = y_d;
    for (int i = 0; i < 8; ++i) {
      const T r2 = x * x + y * y;
      const T radial = T(1.0) + k1 * r2 + k2 * r2 * r2;
      const T x_proj = x * radial;
      const T y_proj = y * radial;
      x += (x_d - x_proj);
      y += (y_d - y_proj);
    }

    // undistorted normalized -> pixel
    const T u_u = x * T(fx_) + T(cx_);
    const T v_u = y * T(fy_) + T(cy_);

    const T denom = ceres::sqrt(T(a_ * a_ + b_ * b_) + T(1e-12));
    residual[0] = T(sqrt_lambda_) * (T(a_) * u_u + T(b_) * v_u + T(c_)) / denom;
    return true;
  }

 private:
  double u_d_;
  double v_d_;
  double fx_;
  double fy_;
  double cx_;
  double cy_;
  double a_;
  double b_;
  double c_;
 double sqrt_lambda_;
};

struct PlumbLineResidualOpencv8 {
  PlumbLineResidualOpencv8(double u_d, double v_d, double a, double b, double c, double sqrt_lambda)
      : u_d_(u_d), v_d_(v_d), a_(a), b_(b), c_(c), sqrt_lambda_(sqrt_lambda) {}

  template <typename T>
  bool operator()(const T* const p, T* residual) const {
    const T fx = p[0];
    const T fy = p[1];
    const T cx = p[2];
    const T cy = p[3];
    const T k1 = p[4];
    const T k2 = p[5];
    const T p1 = p[6];
    const T p2 = p[7];

    const T x_d = (T(u_d_) - cx) / fx;
    const T y_d = (T(v_d_) - cy) / fy;

    T x = x_d;
    T y = y_d;
    for (int i = 0; i < 8; ++i) {
      const T r2 = x * x + y * y;
      const T radial = T(1.0) + k1 * r2 + k2 * r2 * r2;
      const T x_tan = T(2.0) * p1 * x * y + p2 * (r2 + T(2.0) * x * x);
      const T y_tan = p1 * (r2 + T(2.0) * y * y) + T(2.0) * p2 * x * y;
      const T x_proj = x * radial + x_tan;
      const T y_proj = y * radial + y_tan;
      x += (x_d - x_proj);
      y += (y_d - y_proj);
    }

    const T u_u = x * fx + cx;
    const T v_u = y * fy + cy;
    const T denom = ceres::sqrt(T(a_ * a_ + b_ * b_) + T(1e-12));
    residual[0] = T(sqrt_lambda_) * (T(a_) * u_u + T(b_) * v_u + T(c_)) / denom;
    return true;
  }

 private:
  double u_d_;
  double v_d_;
  double a_;
  double b_;
  double c_;
  double sqrt_lambda_;
};

struct ReprojectionResidualOpencv8 {
  ReprojectionResidualOpencv8(double u_obs, double v_obs, double sqrt_lambda)
      : u_obs_(u_obs), v_obs_(v_obs), sqrt_lambda_(sqrt_lambda) {}

  template <typename T>
  bool operator()(const T* const camera, const T* const point, const T* const intrinsics, T* residual) const {
    const T qw = camera[0];
    const T qx = camera[1];
    const T qy = camera[2];
    const T qz = camera[3];
    const T tx = camera[4];
    const T ty = camera[5];
    const T tz = camera[6];

    const T fx = intrinsics[0];
    const T fy = intrinsics[1];
    const T cx = intrinsics[2];
    const T cy = intrinsics[3];
    const T k1 = intrinsics[4];
    const T k2 = intrinsics[5];
    const T p1 = intrinsics[6];
    const T p2 = intrinsics[7];

    const T pw[3] = {point[0], point[1], point[2]};
    T pc[3];
    const T q[4] = {qw, qx, qy, qz};
    ceres::QuaternionRotatePoint(q, pw, pc);
    pc[0] += tx;
    pc[1] += ty;
    pc[2] += tz;

    const T z = pc[2];
    const T inv_z = T(1.0) / (z + T(1e-12));
    const T x = pc[0] * inv_z;
    const T y = pc[1] * inv_z;

    const T r2 = x * x + y * y;
    const T r4 = r2 * r2;
    const T radial = T(1.0) + k1 * r2 + k2 * r4;
    const T x_tan = T(2.0) * p1 * x * y + p2 * (r2 + T(2.0) * x * x);
    const T y_tan = p1 * (r2 + T(2.0) * y * y) + T(2.0) * p2 * x * y;
    const T x_d = x * radial + x_tan;
    const T y_d = y * radial + y_tan;

    const T u = fx * x_d + cx;
    const T v = fy * y_d + cy;

    residual[0] = T(sqrt_lambda_) * (u - T(u_obs_));
    residual[1] = T(sqrt_lambda_) * (v - T(v_obs_));
    return true;
  }

 private:
  double u_obs_;
  double v_obs_;
  double sqrt_lambda_;
};

struct PlumbLineResidualFullBA {
  PlumbLineResidualFullBA(double u_d, double v_d, double a, double b, double c, double sqrt_lambda, int iters = 8)
      : u_d_(u_d), v_d_(v_d), a_(a), b_(b), c_(c), sqrt_lambda_(sqrt_lambda), iters_(iters) {}

  template <typename T>
  bool operator()(const T* const /*camera*/, const T* const /*point*/, const T* const intrinsics, T* residual) const {
    const T fx = intrinsics[0];
    const T fy = intrinsics[1];
    const T cx = intrinsics[2];
    const T cy = intrinsics[3];
    const T k1 = intrinsics[4];
    const T k2 = intrinsics[5];
    const T p1 = intrinsics[6];
    const T p2 = intrinsics[7];

    const T x_d = (T(u_d_) - cx) / fx;
    const T y_d = (T(v_d_) - cy) / fy;

    T x = x_d;
    T y = y_d;
    for (int i = 0; i < iters_; ++i) {
      const T r2 = x * x + y * y;
      const T r4 = r2 * r2;
      const T radial = T(1.0) + k1 * r2 + k2 * r4;
      const T x_tan = T(2.0) * p1 * x * y + p2 * (r2 + T(2.0) * x * x);
      const T y_tan = p1 * (r2 + T(2.0) * y * y) + T(2.0) * p2 * x * y;
      const T x_proj = x * radial + x_tan;
      const T y_proj = y * radial + y_tan;
      x += (x_d - x_proj);
      y += (y_d - y_proj);
    }

    const T u_u = x * fx + cx;
    const T v_u = y * fy + cy;

    const T denom = ceres::sqrt(T(a_ * a_ + b_ * b_) + T(1e-12));
    residual[0] = T(sqrt_lambda_) * (T(a_) * u_u + T(b_) * v_u + T(c_)) / denom;
    return true;
  }

 private:
  double u_d_;
  double v_d_;
  double a_;
  double b_;
  double c_;
  double sqrt_lambda_;
  int iters_;
};

static void RequireShape(const py::buffer_info& info,
                         const std::string& name,
                         const std::vector<ssize_t>& shape) {
  if (static_cast<size_t>(info.ndim) != shape.size()) {
    throw std::runtime_error(name + " must have ndim=" + std::to_string(shape.size()));
  }
  for (size_t i = 0; i < shape.size(); ++i) {
    if (shape[i] >= 0 && info.shape[i] != shape[i]) {
      throw std::runtime_error(name + " has unexpected shape");
    }
  }
}

}  // namespace

py::dict plumbline_refine_full_ba(
    py::array_t<double, py::array::c_style | py::array::forcecast> opencv8,              // (8,)
    py::array_t<double, py::array::c_style | py::array::forcecast> camera_qvec_tvec,     // (C,7)
    py::array_t<double, py::array::c_style | py::array::forcecast> points_xyz,           // (P,3)
    py::array_t<double, py::array::c_style | py::array::forcecast> obs_uv,               // (N,2)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> obs_cam_idx,    // (N,)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> obs_point_idx,  // (N,)
    py::array_t<double, py::array::c_style | py::array::forcecast> pl_sample_uv,         // (M,2)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> pl_sample_line_idx,  // (M,)
    py::array_t<double, py::array::c_style | py::array::forcecast> pl_line_abc,               // (L,3)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> pl_line_cam_idx,     // (L,)
    int image_width,
    int image_height,
    double lambda_reproj,
    double lambda_line,
    double huber_px,
    double cauchy_px,
    int max_num_iterations,
    int num_threads,
    bool refine_intrinsics,
    bool refine_poses,
    bool refine_points) {
  auto intr_info = opencv8.request();
  auto cam_info = camera_qvec_tvec.request();
  auto pt_info = points_xyz.request();
  auto uv_info = obs_uv.request();
  auto cam_idx_info = obs_cam_idx.request();
  auto pt_idx_info = obs_point_idx.request();
  auto pl_uv_info = pl_sample_uv.request();
  auto pl_line_idx_info = pl_sample_line_idx.request();
  auto pl_abc_info = pl_line_abc.request();
  auto pl_line_cam_info = pl_line_cam_idx.request();

  RequireShape(intr_info, "opencv8", {8});
  RequireShape(cam_info, "camera_qvec_tvec", {-1, 7});
  RequireShape(pt_info, "points_xyz", {-1, 3});
  RequireShape(uv_info, "obs_uv", {-1, 2});
  RequireShape(cam_idx_info, "obs_cam_idx", {-1});
  RequireShape(pt_idx_info, "obs_point_idx", {-1});
  RequireShape(pl_uv_info, "pl_sample_uv", {-1, 2});
  RequireShape(pl_line_idx_info, "pl_sample_line_idx", {-1});
  RequireShape(pl_abc_info, "pl_line_abc", {-1, 3});
  RequireShape(pl_line_cam_info, "pl_line_cam_idx", {-1});

  if (image_width <= 0 || image_height <= 0) {
    throw std::runtime_error("image_width/image_height must be > 0");
  }
  if (uv_info.shape[0] != cam_idx_info.shape[0] || uv_info.shape[0] != pt_idx_info.shape[0]) {
    throw std::runtime_error("obs_uv, obs_cam_idx, obs_point_idx must have same length");
  }
  if (pl_uv_info.shape[0] != pl_line_idx_info.shape[0]) {
    throw std::runtime_error("pl_sample_uv and pl_sample_line_idx must have same length");
  }
  if (pl_abc_info.shape[0] != pl_line_cam_info.shape[0]) {
    throw std::runtime_error("pl_line_abc and pl_line_cam_idx must have same length");
  }

  const auto* intr_in = static_cast<const double*>(intr_info.ptr);
  const auto* cam_in = static_cast<const double*>(cam_info.ptr);
  const auto* pt_in = static_cast<const double*>(pt_info.ptr);
  const auto* obs_uv_in = static_cast<const double*>(uv_info.ptr);
  const auto* obs_cam_in = static_cast<const std::int32_t*>(cam_idx_info.ptr);
  const auto* obs_pt_in = static_cast<const std::int32_t*>(pt_idx_info.ptr);
  const auto* pl_uv_in = static_cast<const double*>(pl_uv_info.ptr);
  const auto* pl_line_idx_in = static_cast<const std::int32_t*>(pl_line_idx_info.ptr);
  const auto* pl_abc_in = static_cast<const double*>(pl_abc_info.ptr);
  const auto* pl_line_cam_in = static_cast<const std::int32_t*>(pl_line_cam_info.ptr);

  const std::int64_t C = static_cast<std::int64_t>(cam_info.shape[0]);
  const std::int64_t P = static_cast<std::int64_t>(pt_info.shape[0]);
  const std::int64_t N = static_cast<std::int64_t>(uv_info.shape[0]);
  const std::int64_t M = static_cast<std::int64_t>(pl_uv_info.shape[0]);
  const std::int64_t L = static_cast<std::int64_t>(pl_abc_info.shape[0]);

  std::array<double, 8> intr{};
  std::copy_n(intr_in, 8, intr.data());

  std::vector<double> cameras(static_cast<size_t>(C) * 7);
  std::copy_n(cam_in, cameras.size(), cameras.data());
  for (std::int64_t i = 0; i < C; ++i) {
    double* cptr = cameras.data() + i * 7;
    const double nrm = std::sqrt(cptr[0] * cptr[0] + cptr[1] * cptr[1] + cptr[2] * cptr[2] + cptr[3] * cptr[3]);
    if (nrm > 0.0) {
      cptr[0] /= nrm;
      cptr[1] /= nrm;
      cptr[2] /= nrm;
      cptr[3] /= nrm;
    } else {
      cptr[0] = 1.0;
      cptr[1] = 0.0;
      cptr[2] = 0.0;
      cptr[3] = 0.0;
    }
  }

  std::vector<double> points(static_cast<size_t>(P) * 3);
  std::copy_n(pt_in, points.size(), points.data());

  for (std::int64_t i = 0; i < N; ++i) {
    const std::int32_t c = obs_cam_in[i];
    const std::int32_t p = obs_pt_in[i];
    if (c < 0 || c >= C) {
      throw std::runtime_error("obs_cam_idx contains out-of-range camera index");
    }
    if (p < 0 || p >= P) {
      throw std::runtime_error("obs_point_idx contains out-of-range point index");
    }
  }
  for (std::int64_t i = 0; i < L; ++i) {
    const std::int32_t c = pl_line_cam_in[i];
    if (c < 0 || c >= C) {
      throw std::runtime_error("pl_line_cam_idx contains out-of-range camera index");
    }
  }
  for (std::int64_t i = 0; i < M; ++i) {
    const std::int32_t li = pl_line_idx_in[i];
    if (li < 0 || li >= L) {
      throw std::runtime_error("pl_sample_line_idx contains out-of-range line index");
    }
  }

  ceres::Problem::Options problem_options;
  problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  problem_options.manifold_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  ceres::Problem problem(problem_options);

  ceres::ProductManifold<ceres::QuaternionManifold, ceres::EuclideanManifold<3>> pose_manifold{
      ceres::QuaternionManifold{}, ceres::EuclideanManifold<3>{}};

  problem.AddParameterBlock(intr.data(), 8);
  problem.SetParameterLowerBound(intr.data(), 0, 1e-9);
  problem.SetParameterLowerBound(intr.data(), 1, 1e-9);
  if (!refine_intrinsics) {
    problem.SetParameterBlockConstant(intr.data());
  }

  // Phase-3 stabilization priors (per PROJECT_MEMORY.md):
  // - cx,cy prior to image center with sigma = 2% of dimensions
  // - p1,p2 prior to 0 with sigma = 1e-6
  // - k1,k2 prior to initial (Phase-2) result with sigma = 1e-3
  const double cx0 = 0.5 * static_cast<double>(image_width);
  const double cy0 = 0.5 * static_cast<double>(image_height);
  const double sigma_cx = 0.02 * static_cast<double>(image_width);
  const double sigma_cy = 0.02 * static_cast<double>(image_height);
  const double sigma_p = 1e-6;
  const double sigma_k = 1e-3;
  const double fx0 = intr[0];
  const double fy0 = intr[1];
  const double sigma_fx = 0.05 * std::max(1.0, std::abs(fx0));
  const double sigma_fy = 0.05 * std::max(1.0, std::abs(fy0));
  const double k1_0 = intr[4];
  const double k2_0 = intr[5];

  if (refine_intrinsics) {
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(0, fx0, sigma_fx)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(1, fy0, sigma_fy)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(2, cx0, sigma_cx)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(3, cy0, sigma_cy)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(6, 0.0, sigma_p)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(7, 0.0, sigma_p)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(4, k1_0, sigma_k)),
        nullptr,
        intr.data());
    problem.AddResidualBlock(
        new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(5, k2_0, sigma_k)),
        nullptr,
        intr.data());

    // Keep principal point within the image bounds.
    problem.SetParameterLowerBound(intr.data(), 2, 0.0);
    problem.SetParameterUpperBound(intr.data(), 2, static_cast<double>(image_width));
    problem.SetParameterLowerBound(intr.data(), 3, 0.0);
    problem.SetParameterUpperBound(intr.data(), 3, static_cast<double>(image_height));
  }

  for (std::int64_t i = 0; i < C; ++i) {
    double* cptr = cameras.data() + i * 7;
    problem.AddParameterBlock(cptr, 7, &pose_manifold);
    if (!refine_poses) {
      problem.SetParameterBlockConstant(cptr);
    }
  }

  for (std::int64_t i = 0; i < P; ++i) {
    double* pptr = points.data() + i * 3;
    problem.AddParameterBlock(pptr, 3);
    if (!refine_points) {
      problem.SetParameterBlockConstant(pptr);
    }
  }

  std::unique_ptr<ceres::LossFunction> reproj_loss;
  if (huber_px > 0.0) {
    reproj_loss = std::make_unique<ceres::HuberLoss>(huber_px);
  }

  const double sqrt_lambda_reproj = std::sqrt(std::max(0.0, lambda_reproj));

  for (std::int64_t i = 0; i < N; ++i) {
    const std::int32_t c = obs_cam_in[i];
    const std::int32_t p = obs_pt_in[i];
    const double u = obs_uv_in[2 * i + 0];
    const double v = obs_uv_in[2 * i + 1];

    double* cptr = cameras.data() + static_cast<std::int64_t>(c) * 7;
    double* pptr = points.data() + static_cast<std::int64_t>(p) * 3;
    auto* cost = new ceres::AutoDiffCostFunction<ReprojectionResidualOpencv8, 2, 7, 3, 8>(
        new ReprojectionResidualOpencv8(u, v, sqrt_lambda_reproj));
    problem.AddResidualBlock(cost, reproj_loss.get(), cptr, pptr, intr.data());
  }

  // Plumb-line residual blocks use a shared dummy point block (unused) to keep a uniform 3-block signature.
  double dummy_point[3] = {0.0, 0.0, 0.0};
  problem.AddParameterBlock(dummy_point, 3);
  problem.SetParameterBlockConstant(dummy_point);

  std::unique_ptr<ceres::LossFunction> pl_loss;
  if (cauchy_px > 0.0) {
    pl_loss = std::make_unique<ceres::CauchyLoss>(cauchy_px);
  }

  const double sqrt_lambda_line = std::sqrt(std::max(0.0, lambda_line));
  for (std::int64_t i = 0; i < M; ++i) {
    const double u_d = pl_uv_in[2 * i + 0];
    const double v_d = pl_uv_in[2 * i + 1];
    const std::int32_t li = pl_line_idx_in[i];
    const std::int32_t cam_idx = pl_line_cam_in[li];

    const double a = pl_abc_in[3 * li + 0];
    const double b = pl_abc_in[3 * li + 1];
    const double c = pl_abc_in[3 * li + 2];
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(c)) {
      continue;
    }
    if (a == 0.0 && b == 0.0) {
      continue;
    }

    double* cptr = cameras.data() + static_cast<std::int64_t>(cam_idx) * 7;
    auto* cost = new ceres::AutoDiffCostFunction<PlumbLineResidualFullBA, 1, 7, 3, 8>(
        new PlumbLineResidualFullBA(u_d, v_d, a, b, c, sqrt_lambda_line, 8));
    problem.AddResidualBlock(cost, pl_loss.get(), cptr, dummy_point, intr.data());
  }

  ceres::Solver::Options options;
  options.max_num_iterations = std::max(1, max_num_iterations);
  options.linear_solver_type = ceres::SPARSE_SCHUR;
  options.minimizer_progress_to_stdout = false;
  options.num_threads = std::max(1, num_threads);

  ceres::Solver::Summary summary;
  ceres::Solve(options, &problem, &summary);

  py::array_t<double> out_intr(py::array::ShapeContainer{static_cast<py::ssize_t>(8)});
  {
    auto r = out_intr.mutable_unchecked<1>();
    for (ssize_t i = 0; i < 8; ++i) {
      r(i) = intr[static_cast<size_t>(i)];
    }
  }

  py::array_t<double> out_cams(
      py::array::ShapeContainer{static_cast<py::ssize_t>(C), static_cast<py::ssize_t>(7)});
  {
    auto r = out_cams.mutable_unchecked<2>();
    for (ssize_t i = 0; i < static_cast<ssize_t>(C); ++i) {
      const double* cptr = cameras.data() + i * 7;
      for (ssize_t j = 0; j < 7; ++j) {
        r(i, j) = cptr[j];
      }
    }
  }

  py::array_t<double> out_pts(
      py::array::ShapeContainer{static_cast<py::ssize_t>(P), static_cast<py::ssize_t>(3)});
  {
    auto r = out_pts.mutable_unchecked<2>();
    for (ssize_t i = 0; i < static_cast<ssize_t>(P); ++i) {
      const double* pptr = points.data() + i * 3;
      r(i, 0) = pptr[0];
      r(i, 1) = pptr[1];
      r(i, 2) = pptr[2];
    }
  }

  py::dict out;
  out["success"] = summary.IsSolutionUsable();
  out["opencv8"] = out_intr;
  out["camera_qvec_tvec"] = out_cams;
  out["points_xyz"] = out_pts;
  out["initial_cost"] = summary.initial_cost;
  out["final_cost"] = summary.final_cost;
  out["iterations"] = summary.iterations.size();
  out["brief_report"] = summary.BriefReport();
  out["num_residuals"] = summary.num_residuals;
  out["num_cameras"] = static_cast<std::int64_t>(C);
  out["num_points"] = static_cast<std::int64_t>(P);
  out["num_observations"] = static_cast<std::int64_t>(N);
  out["num_pl_samples"] = static_cast<std::int64_t>(M);
  out["num_pl_lines"] = static_cast<std::int64_t>(L);
  out["lambda_reproj"] = lambda_reproj;
  out["lambda_line"] = lambda_line;
  out["huber_px"] = huber_px;
  out["cauchy_px"] = cauchy_px;
  out["max_num_iterations"] = options.max_num_iterations;
  out["num_threads"] = options.num_threads;
  out["refine_intrinsics"] = refine_intrinsics;
  out["refine_poses"] = refine_poses;
  out["refine_points"] = refine_points;

  // Post-solve plumb-line metrics (median residual, coverage, confidence).
  // NOTE: Uses only intrinsics (pose/point do not affect 2D line constraint as defined).
  std::vector<double> abs_resid;
  abs_resid.reserve(static_cast<size_t>(M));
  std::vector<std::uint8_t> used_lines(static_cast<size_t>(L), 0);
  std::vector<std::uint8_t> grid(64, 0);

  auto undistort_uv = [&](double u_d, double v_d) -> std::array<double, 2> {
    const double fx = intr[0];
    const double fy = intr[1];
    const double cx = intr[2];
    const double cy = intr[3];
    const double k1 = intr[4];
    const double k2 = intr[5];
    const double p1 = intr[6];
    const double p2 = intr[7];

    const double x_d = (u_d - cx) / fx;
    const double y_d = (v_d - cy) / fy;
    double x = x_d;
    double y = y_d;
    for (int it = 0; it < 8; ++it) {
      const double r2 = x * x + y * y;
      const double r4 = r2 * r2;
      const double radial = 1.0 + k1 * r2 + k2 * r4;
      const double x_tan = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x);
      const double y_tan = p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y;
      const double x_proj = x * radial + x_tan;
      const double y_proj = y * radial + y_tan;
      x += (x_d - x_proj);
      y += (y_d - y_proj);
    }
    const double u_u = x * fx + cx;
    const double v_u = y * fy + cy;
    return {u_u, v_u};
  };

  for (std::int64_t i = 0; i < M; ++i) {
    const double u_d = pl_uv_in[2 * i + 0];
    const double v_d = pl_uv_in[2 * i + 1];
    const std::int32_t li = pl_line_idx_in[i];
    if (li < 0 || li >= L) {
      continue;
    }
    const double a = pl_abc_in[3 * li + 0];
    const double b = pl_abc_in[3 * li + 1];
    const double c = pl_abc_in[3 * li + 2];
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(c)) {
      continue;
    }
    if (a == 0.0 && b == 0.0) {
      continue;
    }

    used_lines[static_cast<size_t>(li)] = 1;
    const auto uu = undistort_uv(u_d, v_d);
    const double denom = std::sqrt(a * a + b * b) + 1e-12;
    const double r = (a * uu[0] + b * uu[1] + c) / denom;
    abs_resid.push_back(std::abs(r));

    const double x = std::min(std::max(u_d, 0.0), static_cast<double>(image_width) - 1.0);
    const double y = std::min(std::max(v_d, 0.0), static_cast<double>(image_height) - 1.0);
    const int gx = std::min(7, static_cast<int>(x * 8.0 / static_cast<double>(image_width)));
    const int gy = std::min(7, static_cast<int>(y * 8.0 / static_cast<double>(image_height)));
    grid[static_cast<size_t>(gy * 8 + gx)] = 1;
  }

  double median_pl_px = std::numeric_limits<double>::infinity();
  if (!abs_resid.empty()) {
    const size_t mid = abs_resid.size() / 2;
    std::nth_element(abs_resid.begin(), abs_resid.begin() + mid, abs_resid.end());
    median_pl_px = abs_resid[mid];
  }

  int line_count = 0;
  for (auto v : used_lines) {
    line_count += (v != 0);
  }
  int covered = 0;
  for (auto v : grid) {
    covered += (v != 0);
  }
  const double coverage_spatial = static_cast<double>(covered) / 64.0;
  const double alpha = -std::log(0.9);
  const double confidence_score =
      std::isfinite(median_pl_px) ? (coverage_spatial * std::exp(-alpha * std::max(0.0, median_pl_px))) : 0.0;

  out["median_plumb_line_residual_px"] = median_pl_px;
  out["line_count"] = line_count;
  out["coverage_spatial"] = coverage_spatial;
  out["confidence_score"] = confidence_score;
  return out;
}

py::dict plumbline_refine_opencv8_phase2(
    py::array_t<double, py::array::c_style | py::array::forcecast> sample_uv_distorted, // (N,2)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> line_id,        // (N,)
    py::array_t<double, py::array::c_style | py::array::forcecast> line_abc_undistorted, // (L,3)
    py::array_t<double, py::array::c_style | py::array::forcecast> params_fx_fy_cx_cy_k1_k2_p1_p2, // (8,)
    int image_width,
    int image_height,
    double lambda_line_weight,
    double cauchy_scale_px,
    int max_num_iterations) {
  auto uv_info = sample_uv_distorted.request();
  auto id_info = line_id.request();
  auto abc_info = line_abc_undistorted.request();
  auto p_info = params_fx_fy_cx_cy_k1_k2_p1_p2.request();

  RequireShape(uv_info, "sample_uv_distorted", {-1, 2});
  RequireShape(id_info, "line_id", {-1});
  RequireShape(abc_info, "line_abc_undistorted", {-1, 3});
  RequireShape(p_info, "params_fx_fy_cx_cy_k1_k2_p1_p2", {8});

  if (uv_info.shape[0] != id_info.shape[0]) {
    throw std::runtime_error("sample_uv_distorted and line_id must have same length");
  }
  if (image_width <= 0 || image_height <= 0) {
    throw std::runtime_error("image_width/image_height must be > 0");
  }

  const auto* uv = static_cast<const double*>(uv_info.ptr);
  const auto* ids = static_cast<const std::int32_t*>(id_info.ptr);
  const auto* abc = static_cast<const double*>(abc_info.ptr);
  const auto* p_in = static_cast<const double*>(p_info.ptr);
  const std::int64_t n = static_cast<std::int64_t>(uv_info.shape[0]);
  const std::int64_t l = static_cast<std::int64_t>(abc_info.shape[0]);

  double p[8] = {
      p_in[0], p_in[1], p_in[2], p_in[3], p_in[4], p_in[5], p_in[6], p_in[7],
  };

  ceres::Problem::Options problem_options;
  problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  ceres::Problem problem(problem_options);

  std::unique_ptr<ceres::LossFunction> loss;
  if (cauchy_scale_px > 0.0) {
    loss = std::make_unique<ceres::CauchyLoss>(cauchy_scale_px);
  }

  const double sqrt_lambda = std::sqrt(std::max(0.0, lambda_line_weight));
  for (std::int64_t i = 0; i < n; ++i) {
    const std::int32_t lid = ids[i];
    if (lid < 0 || lid >= l) {
      continue;
    }
    const double u_d = uv[2 * i + 0];
    const double v_d = uv[2 * i + 1];
    const double a = abc[3 * lid + 0];
    const double b = abc[3 * lid + 1];
    const double c = abc[3 * lid + 2];
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(c)) {
      continue;
    }
    if (a == 0.0 && b == 0.0) {
      continue;
    }

    auto* cost = new ceres::AutoDiffCostFunction<PlumbLineResidualOpencv8, 1, 8>(
        new PlumbLineResidualOpencv8(u_d, v_d, a, b, c, sqrt_lambda));
    problem.AddResidualBlock(cost, loss.get(), p);
  }

  // Normal priors per PROJECT_MEMORY.md (Phase 2/3 stabilization):
  // - cx,cy prior to image center with sigma = 2% of dimensions
  // - p1,p2 prior to 0 with sigma = 1e-6
  const double cx0 = 0.5 * static_cast<double>(image_width);
  const double cy0 = 0.5 * static_cast<double>(image_height);
  const double sigma_cx = 0.02 * static_cast<double>(image_width);
  const double sigma_cy = 0.02 * static_cast<double>(image_height);
  const double sigma_p = 1e-6;

  problem.AddResidualBlock(
      new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(2, cx0, sigma_cx)),
      nullptr,
      p);
  problem.AddResidualBlock(
      new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(3, cy0, sigma_cy)),
      nullptr,
      p);
  problem.AddResidualBlock(
      new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(6, 0.0, sigma_p)),
      nullptr,
      p);
  problem.AddResidualBlock(
      new ceres::AutoDiffCostFunction<PriorIndexResidual, 1, 8>(new PriorIndexResidual(7, 0.0, sigma_p)),
      nullptr,
      p);

  // Keep focal lengths positive.
  problem.SetParameterLowerBound(p, 0, 1e-6);
  problem.SetParameterLowerBound(p, 1, 1e-6);

  ceres::Solver::Options options;
  options.max_num_iterations = std::max(1, max_num_iterations);
  options.linear_solver_type = ceres::DENSE_QR;
  options.minimizer_progress_to_stdout = false;
  options.num_threads = 1;

  ceres::Solver::Summary summary;
  ceres::Solve(options, &problem, &summary);

  py::dict out;
  out["success"] = summary.IsSolutionUsable();
  out["fx"] = p[0];
  out["fy"] = p[1];
  out["cx"] = p[2];
  out["cy"] = p[3];
  out["k1"] = p[4];
  out["k2"] = p[5];
  out["p1"] = p[6];
  out["p2"] = p[7];
  out["initial_cost"] = summary.initial_cost;
  out["final_cost"] = summary.final_cost;
  out["iterations"] = summary.iterations.size();
  out["brief_report"] = summary.BriefReport();
  out["num_residuals"] = summary.num_residuals;
  out["cauchy_scale_px"] = cauchy_scale_px;
  out["max_num_iterations"] = options.max_num_iterations;
  out["prior_sigma_cx"] = sigma_cx;
  out["prior_sigma_cy"] = sigma_cy;
  out["prior_sigma_p"] = sigma_p;
  return out;
}

py::dict plumbline_refine_k1k2_bridge(
    py::array_t<double, py::array::c_style | py::array::forcecast> sample_uv_distorted,   // (N,2)
    py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> line_id,          // (N,)
    py::array_t<double, py::array::c_style | py::array::forcecast> line_abc_undistorted,   // (L,3)
    py::array_t<double, py::array::c_style | py::array::forcecast> intrinsics_fx_fy_cx_cy, // (4,)
    py::array_t<double, py::array::c_style | py::array::forcecast> distortion_k1_k2,       // (2,)
    double lambda_line_weight) {
  auto uv_info = sample_uv_distorted.request();
  auto id_info = line_id.request();
  auto abc_info = line_abc_undistorted.request();
  auto intr_info = intrinsics_fx_fy_cx_cy.request();
  auto k_info = distortion_k1_k2.request();

  RequireShape(uv_info, "sample_uv_distorted", {-1, 2});
  RequireShape(id_info, "line_id", {-1});
  RequireShape(abc_info, "line_abc_undistorted", {-1, 3});
  RequireShape(intr_info, "intrinsics_fx_fy_cx_cy", {4});
  RequireShape(k_info, "distortion_k1_k2", {2});

  if (uv_info.shape[0] != id_info.shape[0]) {
    throw std::runtime_error("sample_uv_distorted and line_id must have same length");
  }

  const auto* uv = static_cast<const double*>(uv_info.ptr);
  const auto* ids = static_cast<const std::int32_t*>(id_info.ptr);
  const auto* abc = static_cast<const double*>(abc_info.ptr);
  const auto* intr = static_cast<const double*>(intr_info.ptr);
  const auto* k_init = static_cast<const double*>(k_info.ptr);

  const std::int64_t n = static_cast<std::int64_t>(uv_info.shape[0]);
  const std::int64_t l = static_cast<std::int64_t>(abc_info.shape[0]);

  const double fx = intr[0];
  const double fy = intr[1];
  const double cx = intr[2];
  const double cy = intr[3];

  double k[2] = {k_init[0], k_init[1]};

  ceres::Problem::Options problem_options;
  problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  ceres::Problem problem(problem_options);
  const double sqrt_lambda = std::sqrt(std::max(0.0, lambda_line_weight));

  // Fixed robustifier for Phase-1 bridge (configurable via the legacy entrypoint).
  const double cauchy_scale_px = 2.0;
  std::unique_ptr<ceres::LossFunction> loss = std::make_unique<ceres::CauchyLoss>(cauchy_scale_px);

  for (std::int64_t i = 0; i < n; ++i) {
    const std::int32_t lid = ids[i];
    if (lid < 0 || lid >= l) {
      continue;
    }
    const double u_d = uv[2 * i + 0];
    const double v_d = uv[2 * i + 1];

    const double a = abc[3 * lid + 0];
    const double b = abc[3 * lid + 1];
    const double c = abc[3 * lid + 2];
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(c)) {
      continue;
    }
    if (a == 0.0 && b == 0.0) {
      continue;
    }

    auto* cost = new ceres::AutoDiffCostFunction<PlumbLineResidual, 1, 2>(
        new PlumbLineResidual(u_d, v_d, fx, fy, cx, cy, a, b, c, sqrt_lambda));
    problem.AddResidualBlock(cost, loss.get(), k);
  }

  ceres::Solver::Options options;
  options.max_num_iterations = 50;
  options.linear_solver_type = ceres::DENSE_QR;
  options.minimizer_progress_to_stdout = false;
  options.num_threads = 1;

  ceres::Solver::Summary summary;
  ceres::Solve(options, &problem, &summary);

  py::dict out;
  out["success"] = summary.IsSolutionUsable();
  out["k1"] = k[0];
  out["k2"] = k[1];
  out["initial_cost"] = summary.initial_cost;
  out["final_cost"] = summary.final_cost;
  out["iterations"] = summary.iterations.size();
  out["brief_report"] = summary.BriefReport();
  out["full_report"] = summary.FullReport();
  out["num_residuals"] = summary.num_residuals;
  out["cauchy_scale_px"] = cauchy_scale_px;
  out["max_num_iterations"] = options.max_num_iterations;
  return out;
}

py::dict plumbline_refine_k1k2(py::array_t<double, py::array::c_style | py::array::forcecast> sample_uv,
                               py::array_t<std::int32_t, py::array::c_style | py::array::forcecast> sample_line_id,
                               py::array_t<double, py::array::c_style | py::array::forcecast> line_abc,
                               double fx,
                               double fy,
                               double cx,
                               double cy,
                               double k1,
                               double k2,
                               double lambda_line,
                               double cauchy_scale_px,
                               int max_num_iterations) {
  auto uv_info = sample_uv.request();
  auto id_info = sample_line_id.request();
  auto abc_info = line_abc.request();

  RequireShape(uv_info, "sample_uv", {-1, 2});
  RequireShape(id_info, "sample_line_id", {-1});
  RequireShape(abc_info, "line_abc", {-1, 3});
  if (uv_info.shape[0] != id_info.shape[0]) {
    throw std::runtime_error("sample_uv and sample_line_id must have same length");
  }

  const auto* uv = static_cast<const double*>(uv_info.ptr);
  const auto* ids = static_cast<const std::int32_t*>(id_info.ptr);
  const auto* abc = static_cast<const double*>(abc_info.ptr);
  const std::int64_t n = static_cast<std::int64_t>(uv_info.shape[0]);
  const std::int64_t l = static_cast<std::int64_t>(abc_info.shape[0]);

  double k[2] = {k1, k2};

  ceres::Problem::Options problem_options;
  problem_options.loss_function_ownership = ceres::DO_NOT_TAKE_OWNERSHIP;
  ceres::Problem problem(problem_options);
  const double sqrt_lambda = std::sqrt(std::max(0.0, lambda_line));

  std::unique_ptr<ceres::LossFunction> loss;
  if (cauchy_scale_px > 0.0) {
    loss = std::make_unique<ceres::CauchyLoss>(cauchy_scale_px);
  }

  for (std::int64_t i = 0; i < n; ++i) {
    const std::int32_t lid = ids[i];
    if (lid < 0 || lid >= l) {
      continue;
    }
    const double u_d = uv[2 * i + 0];
    const double v_d = uv[2 * i + 1];

    const double a = abc[3 * lid + 0];
    const double b = abc[3 * lid + 1];
    const double c = abc[3 * lid + 2];
    if (!std::isfinite(a) || !std::isfinite(b) || !std::isfinite(c)) {
      continue;
    }
    if (a == 0.0 && b == 0.0) {
      continue;
    }

    auto* cost = new ceres::AutoDiffCostFunction<PlumbLineResidual, 1, 2>(
        new PlumbLineResidual(u_d, v_d, fx, fy, cx, cy, a, b, c, sqrt_lambda));
    problem.AddResidualBlock(cost, loss.get(), k);
  }

  ceres::Solver::Options options;
  options.max_num_iterations = std::max(1, max_num_iterations);
  options.linear_solver_type = ceres::DENSE_QR;
  options.minimizer_progress_to_stdout = false;
  options.num_threads = 1;

  ceres::Solver::Summary summary;
  ceres::Solve(options, &problem, &summary);

  py::dict out;
  out["success"] = summary.IsSolutionUsable();
  out["k1"] = k[0];
  out["k2"] = k[1];
  out["initial_cost"] = summary.initial_cost;
  out["final_cost"] = summary.final_cost;
  out["iterations"] = summary.iterations.size();
  out["brief_report"] = summary.BriefReport();
  out["full_report"] = summary.FullReport();
  out["num_residuals"] = summary.num_residuals;
  return out;
}

PYBIND11_MODULE(cinetracker_native, m) {
  m.doc() = "Cine-Tracker native extension (Ceres + pybind11)";

  m.def("plumbline_refine_full_ba",
        &plumbline_refine_full_ba,
        py::arg("opencv8"),
        py::arg("camera_qvec_tvec"),
        py::arg("points_xyz"),
        py::arg("obs_uv"),
        py::arg("obs_cam_idx"),
        py::arg("obs_point_idx"),
        py::arg("pl_sample_uv"),
        py::arg("pl_sample_line_idx"),
        py::arg("pl_line_abc"),
        py::arg("pl_line_cam_idx"),
        py::arg("image_width"),
        py::arg("image_height"),
        py::arg("lambda_reproj") = 1.0,
        py::arg("lambda_line") = 1.0,
        py::arg("huber_px") = 2.0,
        py::arg("cauchy_px") = 2.0,
        py::arg("max_num_iterations") = 50,
        py::arg("num_threads") = 1,
        py::arg("refine_intrinsics") = true,
        py::arg("refine_poses") = true,
        py::arg("refine_points") = true);

  m.def("plumbline_refine_opencv8_phase2",
        &plumbline_refine_opencv8_phase2,
        py::arg("sample_uv_distorted"),
        py::arg("line_id"),
        py::arg("line_abc_undistorted"),
        py::arg("params_fx_fy_cx_cy_k1_k2_p1_p2"),
        py::arg("image_width"),
        py::arg("image_height"),
        py::arg("lambda_line_weight"),
        py::arg("cauchy_scale_px") = 2.0,
        py::arg("max_num_iterations") = 50);

  m.def("plumbline_refine_k1k2",
        &plumbline_refine_k1k2_bridge,
        py::arg("sample_uv_distorted"),
        py::arg("line_id"),
        py::arg("line_abc_undistorted"),
        py::arg("intrinsics_fx_fy_cx_cy"),
        py::arg("distortion_k1_k2"),
        py::arg("lambda_line_weight"));

  m.def("plumbline_refine_k1k2",
        &plumbline_refine_k1k2,
        py::arg("sample_uv"),
        py::arg("sample_line_id"),
        py::arg("line_abc"),
        py::arg("fx"),
        py::arg("fy"),
        py::arg("cx"),
        py::arg("cy"),
        py::arg("k1"),
        py::arg("k2"),
        py::arg("lambda_line"),
        py::arg("cauchy_scale_px") = 2.0,
        py::arg("max_num_iterations") = 50);
}
