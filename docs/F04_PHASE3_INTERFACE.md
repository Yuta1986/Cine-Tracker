# F-04 Phase 3 — Native Interface & Data Layout (Draft)

This document defines the **Phase 3** native Ceres entrypoint for **Joint Constrained Bundle Adjustment**:

- Minimize **Reprojection Error + Plumb-Line Error**
- Optimize: shared lens (**OPENCV8**), per-camera poses, and 3D points (with gating to stage optimization)
- Treat line parameters (`pl_line_abc`) as **fixed for one solve call** (outer-loop line refit remains in Python, mirroring Phase 1)

## Python-facing function (pybind11)

Module: `cinetracker_native`

```python
plumbline_refine_full_ba(
    opencv8: np.ndarray,              # (8,) float64
    camera_qvec_tvec: np.ndarray,     # (C,7) float64
    points_xyz: np.ndarray,           # (P,3) float64
    obs_uv: np.ndarray,               # (N,2) float64
    obs_cam_idx: np.ndarray,          # (N,) int32
    obs_point_idx: np.ndarray,        # (N,) int32
    pl_sample_uv: np.ndarray,         # (M,2) float64
    pl_sample_line_idx: np.ndarray,   # (M,) int32
    pl_line_abc: np.ndarray,          # (L,3) float64
    pl_line_cam_idx: np.ndarray,      # (L,) int32
    image_width: int,
    image_height: int,
    lambda_reproj: float,
    lambda_line: float,
    huber_px: float,
    cauchy_px: float,
    max_num_iterations: int,
    num_threads: int,
    refine_intrinsics: bool,
    refine_poses: bool,
    refine_points: bool,
) -> dict
```

## Input arrays (NumPy layout)

All arrays must be **C-contiguous** and use the stated dtypes.

### Shared lens parameters (`opencv8`)

- `opencv8`: `(8,) float64`
- Order: `[fx, fy, cx, cy, k1, k2, p1, p2]`
- Shared across all cameras/images.

### Camera poses (`camera_qvec_tvec`)

- `camera_qvec_tvec`: `(C,7) float64`
- Order per camera: `[qw, qx, qy, qz, tx, ty, tz]`
- Convention: **COLMAP world→camera** transform (same as COLMAP `images.bin`):
  - `X_cam = R(q) * X_world + t`
- Quaternion should be normalized (native code should enforce with a local parameterization).

### 3D points (`points_xyz`)

- `points_xyz`: `(P,3) float64`
- World-space coordinates.

### Reprojection observations (`obs_*`)

Sparse BA layout:

- `obs_uv`: `(N,2) float64` distorted pixel observations
- `obs_cam_idx`: `(N,) int32` 0-based camera index into `camera_qvec_tvec`
- `obs_point_idx`: `(N,) int32` 0-based point index into `points_xyz`

Each row `i` represents one observation of point `obs_point_idx[i]` in camera `obs_cam_idx[i]` at pixel `obs_uv[i]`.

### Plumb-line constraints (`pl_*`)

Lines are associated with a single camera/image. Samples are associated to lines.

- `pl_line_abc`: `(L,3) float64` line parameters `[a,b,c]` in **undistorted pixel space**
  - Intended normalization: `sqrt(a^2+b^2)=1` when possible (not strictly required).
- `pl_line_cam_idx`: `(L,) int32` 0-based camera index for each line.
- `pl_sample_uv`: `(M,2) float64` distorted pixel samples along line segments.
- `pl_sample_line_idx`: `(M,) int32` 0-based index into `pl_line_abc` for each sample.
  - The camera for sample `j` is: `cam = pl_line_cam_idx[pl_sample_line_idx[j]]`.

## Objective (high-level)

Per solve call, Ceres minimizes:

- Reprojection residuals for all `N` observations:
  - `sqrt(lambda_reproj) * robust( reproj(opencv8, pose[c], point[p]) - obs_uv[i] )`
- Plumb-line residuals for all `M` line samples:
  - Undistort `pl_sample_uv[j]` using current `opencv8` and compute distance to fixed line `pl_line_abc[line]`:
  - `sqrt(lambda_line) * robust( a*u_und + b*v_und + c ) / sqrt(a^2+b^2)`

Robust losses:
- Reprojection: Huber with scale `huber_px` (px)
- Plumb-line: Cauchy with scale `cauchy_px` (px)

## Gating / staging semantics

The same entrypoint supports staged optimization:

- `refine_intrinsics=False` → keep `opencv8` fixed
- `refine_poses=False` → keep `camera_qvec_tvec` fixed
- `refine_points=False` → keep `points_xyz` fixed

Phase 3 uses all `True`.

## Return dictionary schema (proposed)

The function returns a Python dict with updated parameters and enough diagnostics to compute `f04_metadata`.
Inputs should be treated as read-only; the function returns updated arrays.

Required keys:
- `success`: `bool`
- `opencv8`: `(8,) float64` updated lens params
- `camera_qvec_tvec`: `(C,7) float64` updated poses
- `points_xyz`: `(P,3) float64` updated points

Solver summary:
- `initial_cost`: `float`
- `final_cost`: `float`
- `iterations`: `int`
- `brief_report`: `str`
- `num_residuals`: `int`

Counts:
- `num_cameras`: `int` (=C)
- `num_points`: `int` (=P)
- `num_observations`: `int` (=N)
- `num_pl_samples`: `int` (=M)
- `num_pl_lines`: `int` (=L)

Residual metrics (for reporting + `f04_metadata`):
- `median_plumb_line_residual_px`: `float`
- `line_count`: `int` (typically `L`)
- `coverage_spatial`: `float` in `[0,1]` (8×8 coverage computed from `pl_sample_uv`)
- `confidence_score`: `float` in `[0,1]` (computed using project formula)

Echoed configuration:
- `lambda_reproj`: `float`
- `lambda_line`: `float`
- `huber_px`: `float`
- `cauchy_px`: `float`
- `max_num_iterations`: `int`
- `num_threads`: `int`
- `refine_intrinsics`: `bool`
- `refine_poses`: `bool`
- `refine_points`: `bool`

Optional (nice-to-have) diagnostics:
- `reproj_rms_px`: `float`
- `reproj_median_px`: `float`
- `plumbline_rms_px`: `float`
- `plumbline_median_px`: `float` (duplicate of required median, if you prefer a consistent naming scheme)

## Notes / constraints

- `obs_cam_idx` and `pl_line_cam_idx` must be within `[0, C)`.
- `obs_point_idx` must be within `[0, P)`.
- `pl_sample_line_idx` must be within `[0, L)`.
- `image_width/image_height` are required for priors and for consistent spatial-coverage scoring.
- If `lambda_reproj=0`, the solve becomes plumb-line-only and will generally be underconstrained for full BA; this is only for debugging.
