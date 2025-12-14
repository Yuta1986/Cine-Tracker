#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <vector>

#include <ceres/ceres.h>
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
