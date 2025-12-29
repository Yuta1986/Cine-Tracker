from __future__ import annotations

import numpy as np

from cinetracker.core.colmap_reader import qvec_to_rotmat


def colmap_w2c_to_c2w_matrix(qvec: np.ndarray, tvec: np.ndarray) -> np.ndarray:
    """
    COLMAP convention:
      X_cam = R * X_world + t   (world -> camera)

    Returns a 4x4 camera-to-world matrix:
      R_c2w = R^T
      C     = -R^T * t
    """

    r_w2c = qvec_to_rotmat(qvec)
    r_c2w = r_w2c.T
    c = -r_c2w @ np.asarray(tvec, dtype=np.float64).reshape(3)
    t = np.eye(4, dtype=np.float64)
    t[:3, :3] = r_c2w
    t[:3, 3] = c
    return t


def colmap_w2c_to_c2w_matrices(qvecs: np.ndarray, tvecs: np.ndarray) -> np.ndarray:
    q = np.asarray(qvecs, dtype=np.float64)
    t = np.asarray(tvecs, dtype=np.float64)
    if q.ndim != 2 or q.shape[1] != 4:
        raise ValueError(f"qvecs must have shape (N,4), got {q.shape}")
    if t.ndim != 2 or t.shape[1] != 3:
        raise ValueError(f"tvecs must have shape (N,3), got {t.shape}")
    mats = np.empty((q.shape[0], 4, 4), dtype=np.float64)
    for i in range(q.shape[0]):
        mats[i] = colmap_w2c_to_c2w_matrix(q[i], t[i])
    return mats


# Basis transform matrix: COLMAP/OpenCV camera axes -> Unreal world axes.
# OpenCV camera axes (COLMAP default camera convention): x right, y down, z forward
# Unreal world axes: X right, Y forward, Z up
#
# Mapping (cv -> ue):
#   X_ue =  X_cv
#   Y_ue =  Z_cv
#   Z_ue = -Y_cv
M_COLMAP_TO_UE = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, -1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)


def apply_basis_transform(world_mats: np.ndarray, m_colmap_to_ue: np.ndarray = M_COLMAP_TO_UE) -> np.ndarray:
    """
    Change-of-basis for transforms:
      T_ue = M * T_colmap * M^{-1}
    """

    t = np.asarray(world_mats, dtype=np.float64)
    if t.ndim != 3 or t.shape[1:] != (4, 4):
        raise ValueError(f"world_mats must have shape (N,4,4), got {t.shape}")
    m = np.asarray(m_colmap_to_ue, dtype=np.float64).reshape(4, 4)
    m_inv = np.linalg.inv(m)
    out = np.empty_like(t)
    for i in range(t.shape[0]):
        out[i] = m @ t[i] @ m_inv
    return out


def write_camera_path_abc(*args, **kwargs) -> None:
    """
    Placeholder for S2.4 Alembic writing.

    We intentionally keep Alembic bindings optional because the correct Python
    package depends on platform/toolchain (e.g., UE bundled Python vs system).
    See docs/S2_4_ALEMBIC.md for the exact PyAlembic calls.
    """

    raise RuntimeError("Alembic Python bindings not wired yet; see docs/S2_4_ALEMBIC.md")
