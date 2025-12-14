from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable, TextIO

import numpy as np

from cinetracker.core.colmap_reader import COLMAPReader
from cinetracker.core.lens_json import opencv_intrinsics_from_colmap_camera


@dataclass(frozen=True)
class PlumbLineInput:
    sample_uv: np.ndarray  # (N,2) float64 distorted pixels
    sample_line_id: np.ndarray  # (N,) int32
    num_lines: int
    image_width: int
    image_height: int
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float


@dataclass(frozen=True)
class PlumbLineIterationMetrics:
    outer_iter: int
    k1: float
    k2: float
    median_line_px: float
    lambda_line: float


CONF_ALPHA: float = -math.log(0.9)


def compute_spatial_coverage(
    sample_uv: np.ndarray,
    *,
    image_width: int,
    image_height: int,
    grid: int = 8,
) -> float:
    pts = np.asarray(sample_uv, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"sample_uv must have shape (N,2), got {pts.shape}")
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image_width/image_height must be > 0")
    g = int(grid)
    if g <= 0:
        raise ValueError("grid must be > 0")
    if pts.size == 0:
        return 0.0

    x = np.clip(pts[:, 0], 0.0, float(image_width) - 1.0)
    y = np.clip(pts[:, 1], 0.0, float(image_height) - 1.0)
    gx = np.minimum(g - 1, (x * g / float(image_width)).astype(np.int32))
    gy = np.minimum(g - 1, (y * g / float(image_height)).astype(np.int32))
    cells = np.unique(gy * g + gx)
    return float(cells.size) / float(g * g)


def compute_confidence_score(*, coverage: float, median_plumb_line_residual_px: float, alpha: float = CONF_ALPHA) -> float:
    c = float(np.clip(float(coverage), 0.0, 1.0))
    e = float(median_plumb_line_residual_px)
    if not np.isfinite(e):
        return 0.0
    return float(c * math.exp(-float(alpha) * max(0.0, e)))


def compute_f04_metadata(
    pl: PlumbLineInput,
    *,
    final_k1: float,
    final_k2: float,
) -> dict[str, float | int]:
    und = undistort_points_k1k2_fixed_point(
        pl.sample_uv, fx=pl.fx, fy=pl.fy, cx=pl.cx, cy=pl.cy, k1=float(final_k1), k2=float(final_k2), iterations=8
    )
    line_abc = fit_lines_tls_abc(und, pl.sample_line_id, pl.num_lines)
    resid = point_to_line_distance_px(und, line_abc, pl.sample_line_id)
    median_px = float(np.median(np.abs(resid))) if resid.size else float("inf")
    coverage = compute_spatial_coverage(pl.sample_uv, image_width=pl.image_width, image_height=pl.image_height, grid=8)
    score = compute_confidence_score(coverage=coverage, median_plumb_line_residual_px=median_px)
    return {
        "confidence_score": float(score),
        "median_plumb_line_residual_px": float(median_px),
        "line_count": int(pl.num_lines),
    }


def _require_opencv() -> "object":
    try:
        import cv2  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("F-04 plumb-line prototype requires OpenCV. Install with `pip install opencv-python`.") from e
    return cv2


def _iter_image_files(images_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    files = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(files)


def detect_lines_lsd(
    image_bgr: np.ndarray,
    *,
    min_length_px: float,
    max_lines: int,
) -> np.ndarray:
    cv2 = _require_opencv()
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines, _, _, _ = lsd.detect(gray)
    if lines is None:
        return np.zeros((0, 4), dtype=np.float64)
    segs = lines.reshape(-1, 4).astype(np.float64, copy=False)
    dx = segs[:, 2] - segs[:, 0]
    dy = segs[:, 3] - segs[:, 1]
    lengths = np.hypot(dx, dy)
    keep = lengths >= float(min_length_px)
    segs = segs[keep]
    lengths = lengths[keep]
    if segs.size == 0:
        return np.zeros((0, 4), dtype=np.float64)
    order = np.argsort(-lengths)
    segs = segs[order]
    if max_lines > 0:
        segs = segs[:max_lines]
    return np.ascontiguousarray(segs, dtype=np.float64)


def sample_points_on_segments(
    segments_xyxy: np.ndarray,
    *,
    step_px: float,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns:
      sample_uv: (N,2) float64
      sample_line_id: (N,) int32
    """
    segs = np.asarray(segments_xyxy, dtype=np.float64)
    if segs.ndim != 2 or segs.shape[1] != 4:
        raise ValueError(f"segments_xyxy must have shape (M,4), got {segs.shape}")

    step = float(step_px)
    if step <= 0:
        raise ValueError("step_px must be > 0")

    samples: list[np.ndarray] = []
    line_ids: list[np.ndarray] = []
    for i, (x1, y1, x2, y2) in enumerate(segs):
        dx = x2 - x1
        dy = y2 - y1
        length = float(np.hypot(dx, dy))
        if length <= 1e-9:
            continue
        n = max(2, int(np.floor(length / step)) + 1)
        t = np.linspace(0.0, 1.0, n, dtype=np.float64)
        pts = np.stack([x1 + t * dx, y1 + t * dy], axis=1)
        samples.append(pts)
        line_ids.append(np.full((pts.shape[0],), i, dtype=np.int32))

    if not samples:
        return np.zeros((0, 2), dtype=np.float64), np.zeros((0,), dtype=np.int32)
    sample_uv = np.ascontiguousarray(np.concatenate(samples, axis=0), dtype=np.float64)
    sample_line_id = np.ascontiguousarray(np.concatenate(line_ids, axis=0), dtype=np.int32)
    return sample_uv, sample_line_id


def undistort_points_k1k2_fixed_point(
    uv: np.ndarray,
    *,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    k1: float,
    k2: float,
    iterations: int = 8,
) -> np.ndarray:
    pts = np.asarray(uv, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"uv must have shape (N,2), got {pts.shape}")

    x_d = (pts[:, 0] - cx) / fx
    y_d = (pts[:, 1] - cy) / fy
    x = x_d.copy()
    y = y_d.copy()
    for _ in range(int(iterations)):
        r2 = x * x + y * y
        radial = 1.0 + k1 * r2 + k2 * r2 * r2
        x_proj = x * radial
        y_proj = y * radial
        x += x_d - x_proj
        y += y_d - y_proj
    u_u = x * fx + cx
    v_u = y * fy + cy
    return np.stack([u_u, v_u], axis=1)


def undistort_points_opencv8_fixed_point(
    uv: np.ndarray,
    *,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    k1: float,
    k2: float,
    p1: float,
    p2: float,
    iterations: int = 8,
) -> np.ndarray:
    pts = np.asarray(uv, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"uv must have shape (N,2), got {pts.shape}")

    x_d = (pts[:, 0] - cx) / fx
    y_d = (pts[:, 1] - cy) / fy
    x = x_d.copy()
    y = y_d.copy()
    for _ in range(int(iterations)):
        r2 = x * x + y * y
        r4 = r2 * r2
        radial = 1.0 + k1 * r2 + k2 * r4
        x_tan = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
        y_tan = p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
        x_proj = x * radial + x_tan
        y_proj = y * radial + y_tan
        x += x_d - x_proj
        y += y_d - y_proj
    u_u = x * fx + cx
    v_u = y * fy + cy
    return np.stack([u_u, v_u], axis=1)


def fit_lines_tls_abc(undistorted_uv: np.ndarray, sample_line_id: np.ndarray, num_lines: int) -> np.ndarray:
    """
    Total least squares line fit (in pixel space) for each line id.
    Returns (L,3) [a,b,c] with sqrt(a^2+b^2)=1 when possible.
    """
    pts = np.asarray(undistorted_uv, dtype=np.float64)
    ids = np.asarray(sample_line_id, dtype=np.int32)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"undistorted_uv must have shape (N,2), got {pts.shape}")
    if ids.ndim != 1 or ids.shape[0] != pts.shape[0]:
        raise ValueError(f"sample_line_id must have shape (N,), got {ids.shape}")
    if num_lines <= 0:
        raise ValueError("num_lines must be > 0")

    out = np.zeros((num_lines, 3), dtype=np.float64)
    for lid in range(num_lines):
        mask = ids == lid
        if not np.any(mask):
            continue
        p = pts[mask]
        if p.shape[0] < 2:
            continue
        mean = p.mean(axis=0)
        x = p - mean
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        direction = vt[0]
        normal = np.array([-direction[1], direction[0]], dtype=np.float64)
        nrm = float(np.hypot(normal[0], normal[1]))
        if nrm <= 1e-12:
            continue
        normal /= nrm
        a, b = float(normal[0]), float(normal[1])
        c = -a * float(mean[0]) - b * float(mean[1])
        out[lid] = [a, b, c]
    return out


def point_to_line_distance_px(uv: np.ndarray, line_abc: np.ndarray, line_id: np.ndarray) -> np.ndarray:
    pts = np.asarray(uv, dtype=np.float64)
    abc = np.asarray(line_abc, dtype=np.float64)
    ids = np.asarray(line_id, dtype=np.int32)
    if pts.ndim != 2 or pts.shape[1] != 2:
        raise ValueError(f"uv must have shape (N,2), got {pts.shape}")
    if abc.ndim != 2 or abc.shape[1] != 3:
        raise ValueError(f"line_abc must have shape (L,3), got {abc.shape}")
    if ids.ndim != 1 or ids.shape[0] != pts.shape[0]:
        raise ValueError(f"line_id must have shape (N,), got {ids.shape}")
    a = abc[ids, 0]
    b = abc[ids, 1]
    c = abc[ids, 2]
    denom = np.sqrt(a * a + b * b) + 1e-12
    return (a * pts[:, 0] + b * pts[:, 1] + c) / denom


@dataclass(frozen=True)
class SparseBAInputs:
    opencv8: np.ndarray  # (8,) float64
    camera_qvec_tvec: np.ndarray  # (C,7) float64
    points_xyz: np.ndarray  # (P,3) float64
    obs_uv: np.ndarray  # (N,2) float64
    obs_cam_idx: np.ndarray  # (N,) int32
    obs_point_idx: np.ndarray  # (N,) int32
    image_width: int
    image_height: int
    image_ids: np.ndarray  # (C,) int32 in same order as camera_qvec_tvec
    image_names: list[str]  # (C,)


def build_sparse_ba_inputs_from_colmap_model(*, model_dir: str | Path) -> SparseBAInputs:
    reader = COLMAPReader(model_dir)
    cameras = reader.read_cameras_bin()
    images = reader.read_images_bin()
    points3d = reader.read_points3d_bin()

    if not images:
        raise RuntimeError("COLMAP model has no images")
    if not cameras:
        raise RuntimeError("COLMAP model has no cameras")

    image_items = sorted(images.values(), key=lambda im: im.image_id)
    camera_ids = {im.camera_id for im in image_items}
    if len(camera_ids) != 1:
        raise RuntimeError(f"Phase 3 currently requires a single shared camera_id; got {sorted(camera_ids)}")

    cam_id = next(iter(camera_ids))
    cam = cameras.get(cam_id)
    if cam is None:
        raise RuntimeError(f"camera_id {cam_id} referenced by images.bin not found in cameras.bin")

    opencv = opencv_intrinsics_from_colmap_camera(
        model_name=cam.model_name,
        width=cam.width,
        height=cam.height,
        params=[float(x) for x in cam.params.tolist()],
    )
    opencv8 = np.array(
        [opencv.fx, opencv.fy, opencv.cx, opencv.cy, opencv.k1, opencv.k2, opencv.p1, opencv.p2],
        dtype=np.float64,
    )

    image_id_to_cam_idx = {im.image_id: i for i, im in enumerate(image_items)}
    camera_qvec_tvec = np.zeros((len(image_items), 7), dtype=np.float64)
    for i, im in enumerate(image_items):
        camera_qvec_tvec[i, 0:4] = im.qvec.astype(np.float64, copy=False)
        camera_qvec_tvec[i, 4:7] = im.tvec.astype(np.float64, copy=False)

    point_items = sorted(points3d.values(), key=lambda p: p.point3D_id)
    if not point_items:
        raise RuntimeError("COLMAP model has no 3D points (points3D.bin empty)")

    point_id_to_idx = {p.point3D_id: i for i, p in enumerate(point_items)}
    points_xyz = np.stack([p.xyz for p in point_items], axis=0).astype(np.float64, copy=False)

    obs_uv: list[list[float]] = []
    obs_cam_idx: list[int] = []
    obs_point_idx: list[int] = []

    for p in point_items:
        p_idx = point_id_to_idx[p.point3D_id]
        for image_id, point2d_idx in zip(p.track_image_ids.tolist(), p.track_point2D_idxs.tolist(), strict=True):
            im = images.get(int(image_id))
            if im is None:
                continue
            cam_idx = image_id_to_cam_idx.get(im.image_id)
            if cam_idx is None:
                continue
            if int(point2d_idx) < 0 or int(point2d_idx) >= im.xys.shape[0]:
                continue
            if int(im.point3D_ids[int(point2d_idx)]) != int(p.point3D_id):
                continue
            xy = im.xys[int(point2d_idx)]
            obs_uv.append([float(xy[0]), float(xy[1])])
            obs_cam_idx.append(int(cam_idx))
            obs_point_idx.append(int(p_idx))

    if not obs_uv:
        raise RuntimeError("No valid 2D-3D observations could be constructed from points3D tracks")

    return SparseBAInputs(
        opencv8=np.ascontiguousarray(opencv8, dtype=np.float64),
        camera_qvec_tvec=np.ascontiguousarray(camera_qvec_tvec, dtype=np.float64),
        points_xyz=np.ascontiguousarray(points_xyz, dtype=np.float64),
        obs_uv=np.ascontiguousarray(np.array(obs_uv, dtype=np.float64), dtype=np.float64),
        obs_cam_idx=np.ascontiguousarray(np.array(obs_cam_idx, dtype=np.int32), dtype=np.int32),
        obs_point_idx=np.ascontiguousarray(np.array(obs_point_idx, dtype=np.int32), dtype=np.int32),
        image_width=int(cam.width),
        image_height=int(cam.height),
        image_ids=np.ascontiguousarray(np.array([im.image_id for im in image_items], dtype=np.int32), dtype=np.int32),
        image_names=[im.name for im in image_items],
    )


@dataclass(frozen=True)
class PlumbLineBAInputs:
    pl_sample_uv: np.ndarray  # (M,2) float64 distorted pixels
    pl_sample_line_idx: np.ndarray  # (M,) int32
    pl_line_abc: np.ndarray  # (L,3) float64 line params in undistorted pixel space
    pl_line_cam_idx: np.ndarray  # (L,) int32 camera index for each line


def refit_pl_line_abc_from_samples(
    pl_sample_uv: np.ndarray,
    pl_sample_line_idx: np.ndarray,
    *,
    num_lines: int,
    opencv8: np.ndarray,
) -> np.ndarray:
    fx, fy, cx, cy, k1, k2, p1, p2 = [float(x) for x in np.asarray(opencv8, dtype=np.float64).reshape(8)]
    und = undistort_points_opencv8_fixed_point(
        pl_sample_uv, fx=fx, fy=fy, cx=cx, cy=cy, k1=k1, k2=k2, p1=p1, p2=p2, iterations=8
    )
    if not np.all(np.isfinite(und)):
        raise RuntimeError("Undistortion produced non-finite values; intrinsics likely diverged")
    return np.ascontiguousarray(fit_lines_tls_abc(und, pl_sample_line_idx, int(num_lines)), dtype=np.float64)


def build_plumbline_input_from_images(
    *,
    images_dir: str | Path,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    k1: float,
    k2: float,
    max_images: int,
    max_lines_per_image: int,
    min_line_length_px: float,
    sample_step_px: float,
    out: TextIO,
) -> PlumbLineInput:
    images_dir = Path(images_dir)
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Images dir not found: {images_dir}")

    files = _iter_image_files(images_dir)
    if max_images > 0:
        files = files[:max_images]
    if not files:
        raise RuntimeError(f"No images found in: {images_dir}")

    cv2 = _require_opencv()
    all_samples: list[np.ndarray] = []
    all_ids: list[np.ndarray] = []
    line_offset = 0
    total_lines = 0
    image_width = 0
    image_height = 0

    for i, p in enumerate(files):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        if image_width == 0:
            h, w = img.shape[:2]
            image_width = int(w)
            image_height = int(h)
        segs = detect_lines_lsd(img, min_length_px=min_line_length_px, max_lines=max_lines_per_image)
        if segs.shape[0] == 0:
            continue
        uv, lid = sample_points_on_segments(segs, step_px=sample_step_px)
        if uv.shape[0] == 0:
            continue
        lid = lid + np.int32(line_offset)
        all_samples.append(uv)
        all_ids.append(lid)
        total_lines += int(segs.shape[0])
        line_offset += int(segs.shape[0])
        print(f"[f04] {p.name}: lines={segs.shape[0]} samples={uv.shape[0]}", file=out)

    if not all_samples:
        raise RuntimeError("No usable lines found (try lowering min length / increasing max lines).")
    if image_width <= 0 or image_height <= 0:
        raise RuntimeError("Failed to read image dimensions from inputs.")

    sample_uv = np.ascontiguousarray(np.concatenate(all_samples, axis=0), dtype=np.float64)
    sample_line_id = np.ascontiguousarray(np.concatenate(all_ids, axis=0), dtype=np.int32)
    return PlumbLineInput(
        sample_uv=sample_uv,
        sample_line_id=sample_line_id,
        num_lines=total_lines,
        image_width=image_width,
        image_height=image_height,
        fx=float(fx),
        fy=float(fy),
        cx=float(cx),
        cy=float(cy),
        k1=float(k1),
        k2=float(k2),
    )


def build_plumbline_ba_inputs_from_colmap_images(
    *,
    images_root: str | Path,
    image_names: list[str],
    opencv8: np.ndarray,
    max_images: int,
    max_lines_per_image: int,
    min_line_length_px: float,
    sample_step_px: float,
    out: TextIO,
) -> PlumbLineBAInputs:
    """
    Builds Phase-3 plumb-line inputs from COLMAP image names, associating each detected segment to a camera index.

    Policy:
    - Detect LSD segments per image in distorted pixel space.
    - Sample points on each segment in distorted pixel space.
    - Undistort sampled points using current OPENCV8 via fixed-point iterations.
    - Fit line_abc in undistorted pixel space (TLS).
    - Return global line indexing with per-line camera association.
    """
    images_root = Path(images_root)
    if not images_root.is_dir():
        raise FileNotFoundError(f"images_root not found: {images_root}")

    fx, fy, cx, cy, k1, k2, p1, p2 = [float(x) for x in np.asarray(opencv8, dtype=np.float64).reshape(8)]

    cv2 = _require_opencv()
    all_sample_uv: list[np.ndarray] = []
    all_sample_line_idx: list[np.ndarray] = []
    all_line_abc: list[np.ndarray] = []
    all_line_cam_idx: list[np.ndarray] = []

    line_offset = 0
    names = list(image_names)
    if max_images > 0:
        names = names[:max_images]

    for cam_idx, name in enumerate(names):
        p = images_root / name
        if not p.exists():
            p = images_root / Path(name).name
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
        segs = detect_lines_lsd(img, min_length_px=min_line_length_px, max_lines=max_lines_per_image)
        if segs.shape[0] == 0:
            continue
        sample_uv, local_line_id = sample_points_on_segments(segs, step_px=sample_step_px)
        if sample_uv.shape[0] == 0:
            continue
        und = undistort_points_opencv8_fixed_point(
            sample_uv, fx=fx, fy=fy, cx=cx, cy=cy, k1=k1, k2=k2, p1=p1, p2=p2, iterations=8
        )
        line_abc = fit_lines_tls_abc(und, local_line_id, int(segs.shape[0]))

        global_line_id = local_line_id + np.int32(line_offset)
        all_sample_uv.append(sample_uv)
        all_sample_line_idx.append(global_line_id)
        all_line_abc.append(line_abc)
        all_line_cam_idx.append(np.full((line_abc.shape[0],), cam_idx, dtype=np.int32))

        print(f"[f04-ba] {p.name}: lines={segs.shape[0]} samples={sample_uv.shape[0]}", file=out)
        line_offset += int(segs.shape[0])

    if not all_sample_uv:
        raise RuntimeError("No usable plumb-line samples found (try lowering min length / increasing max lines).")

    pl_sample_uv = np.ascontiguousarray(np.concatenate(all_sample_uv, axis=0), dtype=np.float64)
    pl_sample_line_idx = np.ascontiguousarray(np.concatenate(all_sample_line_idx, axis=0), dtype=np.int32)
    pl_line_abc = np.ascontiguousarray(np.concatenate(all_line_abc, axis=0), dtype=np.float64)
    pl_line_cam_idx = np.ascontiguousarray(np.concatenate(all_line_cam_idx, axis=0), dtype=np.int32)
    return PlumbLineBAInputs(
        pl_sample_uv=pl_sample_uv,
        pl_sample_line_idx=pl_sample_line_idx,
        pl_line_abc=pl_line_abc,
        pl_line_cam_idx=pl_line_cam_idx,
    )


def f04_hybrid_bundle_adjustment(
    *,
    model_dir: str | Path,
    images_root: str | Path,
    lambda_reproj: float = 1.0,
    lambda_line: float = 1.0,
    huber_px: float = 2.0,
    cauchy_px: float = 2.0,
    max_num_iterations: int = 50,
    num_threads: int = 1,
    refine_intrinsics: bool = True,
    refine_poses: bool = True,
    refine_points: bool = True,
    max_images: int = 0,
    max_lines_per_image: int = 200,
    min_line_length_px: float = 120.0,
    sample_step_px: float = 8.0,
    outer_iters: int = 3,
    out: TextIO | None = None,
) -> dict[str, object]:
    """
    Phase 3 wrapper: extract sparse BA arrays from a COLMAP model and plumb-line arrays from images,
    call the native Ceres solver, and return updated arrays plus `f04_metadata`.

    Inputs:
    - `model_dir`: COLMAP sparse model directory containing `cameras.bin/images.bin/points3D.bin`
    - `images_root`: directory containing images referenced by `images.bin` (by name)

    Output (high-level):
    - `opencv8`, `camera_qvec_tvec`, `points_xyz`: updated NumPy arrays from native solver
    - `native`: raw native return dict
    - `f04_metadata`: dict compatible with PROJECT_MEMORY.md spec
    """
    from cinetracker.native import require_native

    if out is None:
        import sys

        out = sys.stdout

    ba = build_sparse_ba_inputs_from_colmap_model(model_dir=model_dir)
    pl0 = build_plumbline_ba_inputs_from_colmap_images(
        images_root=images_root,
        image_names=ba.image_names,
        opencv8=ba.opencv8,
        max_images=max_images,
        max_lines_per_image=max_lines_per_image,
        min_line_length_px=min_line_length_px,
        sample_step_px=sample_step_px,
        out=out,
    )

    native = require_native()

    opencv8 = ba.opencv8.copy()
    camera_qvec_tvec = ba.camera_qvec_tvec.copy()
    points_xyz = ba.points_xyz.copy()
    pl_sample_uv = pl0.pl_sample_uv
    pl_sample_line_idx = pl0.pl_sample_line_idx
    pl_line_cam_idx = pl0.pl_line_cam_idx

    res: object | None = None
    for it in range(max(1, int(outer_iters))):
        pl_line_abc = refit_pl_line_abc_from_samples(
            pl_sample_uv, pl_sample_line_idx, num_lines=int(pl_line_cam_idx.shape[0]), opencv8=opencv8
        )
        res = native.plumbline_refine_full_ba(
            opencv8,
            camera_qvec_tvec,
            points_xyz,
            ba.obs_uv,
            ba.obs_cam_idx,
            ba.obs_point_idx,
            pl_sample_uv,
            pl_sample_line_idx,
            pl_line_abc,
            pl_line_cam_idx,
            ba.image_width,
            ba.image_height,
            float(lambda_reproj),
            float(lambda_line),
            float(huber_px),
            float(cauchy_px),
            int(max_num_iterations),
            int(num_threads),
            bool(refine_intrinsics),
            bool(refine_poses),
            bool(refine_points),
        )

        opencv8 = np.asarray(res["opencv8"], dtype=np.float64)
        camera_qvec_tvec = np.asarray(res["camera_qvec_tvec"], dtype=np.float64)
        points_xyz = np.asarray(res["points_xyz"], dtype=np.float64)
        print(f"[f04-ba] outer_iter={it} cost={float(res.get('final_cost', float('nan'))):.6g}", file=out)

    assert isinstance(res, dict)
    f04_metadata = {
        "confidence_score": float(res.get("confidence_score", 0.0)),
        "median_plumb_line_residual_px": float(res.get("median_plumb_line_residual_px", float("inf"))),
        "line_count": int(res.get("line_count", 0)),
    }

    return {
        "opencv8": opencv8,
        "camera_qvec_tvec": camera_qvec_tvec,
        "points_xyz": points_xyz,
        "native": res,
        "f04_metadata": f04_metadata,
    }


def refine_k1k2_plumbline_only(
    pl: PlumbLineInput,
    *,
    outer_iters: int,
    median_reproj_px: float,
    lambda_cap: float,
    cauchy_scale_px: float,
    out: TextIO,
) -> tuple[float, float, list[PlumbLineIterationMetrics]]:
    """
    Outer-loop:
      1) Undistort sample points with current (k1,k2)
      2) Fit fixed line (a,b,c) per detected segment id
      3) Run a Ceres step optimizing (k1,k2) only, with fixed lines for this iter
    """
    from cinetracker.native import require_native

    native = require_native()

    k1, k2 = float(pl.k1), float(pl.k2)
    metrics: list[PlumbLineIterationMetrics] = []
    for it in range(int(outer_iters)):
        und = undistort_points_k1k2_fixed_point(
            pl.sample_uv, fx=pl.fx, fy=pl.fy, cx=pl.cx, cy=pl.cy, k1=k1, k2=k2, iterations=8
        )
        line_abc = fit_lines_tls_abc(und, pl.sample_line_id, pl.num_lines)
        resid = point_to_line_distance_px(und, line_abc, pl.sample_line_id)
        median_line_px = float(np.median(np.abs(resid))) if resid.size else float("inf")
        lambda_line = 0.1 * (float(median_reproj_px) / max(median_line_px, 1e-6))
        lambda_line = min(float(lambda_cap), max(0.0, lambda_line))

        print(
            f"[f04] iter={it} k1={k1:.6g} k2={k2:.6g} median_line_px={median_line_px:.4g} lambda={lambda_line:.4g}",
            file=out,
        )
        metrics.append(
            PlumbLineIterationMetrics(
                outer_iter=it,
                k1=k1,
                k2=k2,
                median_line_px=median_line_px,
                lambda_line=lambda_line,
            )
        )

        if not np.isfinite(median_line_px) or median_line_px <= 0:
            break

        res = native.plumbline_refine_k1k2(
            sample_uv=pl.sample_uv,
            sample_line_id=pl.sample_line_id,
            line_abc=line_abc,
            fx=pl.fx,
            fy=pl.fy,
            cx=pl.cx,
            cy=pl.cy,
            k1=k1,
            k2=k2,
            lambda_line=lambda_line,
            cauchy_scale_px=float(cauchy_scale_px),
        )
        k1, k2 = float(res["k1"]), float(res["k2"])

    return k1, k2, metrics
