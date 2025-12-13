from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO

import numpy as np


@dataclass(frozen=True)
class PlumbLineInput:
    sample_uv: np.ndarray  # (N,2) float64 distorted pixels
    sample_line_id: np.ndarray  # (N,) int32
    num_lines: int
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

    for i, p in enumerate(files):
        img = cv2.imread(str(p), cv2.IMREAD_COLOR)
        if img is None:
            continue
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

    sample_uv = np.ascontiguousarray(np.concatenate(all_samples, axis=0), dtype=np.float64)
    sample_line_id = np.ascontiguousarray(np.concatenate(all_ids, axis=0), dtype=np.int32)
    return PlumbLineInput(
        sample_uv=sample_uv,
        sample_line_id=sample_line_id,
        num_lines=total_lines,
        fx=float(fx),
        fy=float(fy),
        cx=float(cx),
        cy=float(cy),
        k1=float(k1),
        k2=float(k2),
    )


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

