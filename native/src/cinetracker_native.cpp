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

  ceres::Problem problem;
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

