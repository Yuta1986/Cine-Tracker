# S2.4 — Alembic Conversion (Pose Inversion + UE Basis)

This doc provides the exact linear algebra and the PyAlembic API call structure needed for exporting `camera_path.abc`.

## 1) Pose conversion: COLMAP → Camera-to-World matrices

COLMAP stores a per-image pose (world→camera):

`X_cam = R * X_world + t`

Therefore:
- `R_c2w = R^T`
- `C = -R^T * t`

NumPy snippet (for all frames):

```python
import numpy as np
from cinetracker.core.colmap_reader import qvec_to_rotmat

def w2c_to_c2w(qvecs: np.ndarray, tvecs: np.ndarray) -> np.ndarray:
    # qvecs shape (N,4), tvecs shape (N,3)
    N = qvecs.shape[0]
    out = np.empty((N, 4, 4), dtype=np.float64)
    for i in range(N):
        R = qvec_to_rotmat(qvecs[i])      # world->camera
        Rc2w = R.T                        # inverse rotation
        C = -Rc2w @ tvecs[i].reshape(3)   # inverse translation
        T = np.eye(4, dtype=np.float64)
        T[:3,:3] = Rc2w
        T[:3, 3] = C
        out[i] = T
    return out
```

Reference implementation: `src/cinetracker/core/pose_alembic.py`

## 2) Coordinate basis transform: `M_COLMAP→UE`

We apply a fixed basis transform to reconcile COLMAP/OpenCV camera axes with Unreal’s commonly used axes.

Assumptions:
- OpenCV camera axes: **x right, y down, z forward**
- Unreal world axes: **X right, Y forward, Z up**

Mapping:
- `X_ue = X_cv`
- `Y_ue = Z_cv`
- `Z_ue = -Y_cv`

Matrix:

```python
M = np.array([
  [1,  0,  0, 0],
  [0,  0,  1, 0],
  [0, -1,  0, 0],
  [0,  0,  0, 1],
], dtype=np.float64)

T_c2w_ue = M @ T_c2w_colmap @ np.linalg.inv(M)
```

This is implemented as `apply_basis_transform()` in `src/cinetracker/core/pose_alembic.py`.

## 3) PyAlembic writing (time-sampled world matrices)

Alembic Python bindings vary by environment. The typical API (ILM Alembic) looks like this:

```python
import alembic.Abc as Abc
import alembic.AbcGeom as AbcGeom

def write_camera_abc(path: str, world_mats: np.ndarray, fps: float):
    archive = Abc.OArchive(path)
    top = archive.getTop()

    ts = Abc.TimeSampling(1.0 / fps, 0.0)
    ts_index = archive.addTimeSampling(ts)

    xform_obj = AbcGeom.OXform(top, "CameraXform")
    xform_schema = xform_obj.getSchema()
    xform_schema.setTimeSampling(ts_index)

    cam_obj = AbcGeom.OCamera(xform_obj, "Camera")
    cam_schema = cam_obj.getSchema()
    cam_schema.setTimeSampling(ts_index)

    for i in range(world_mats.shape[0]):
        M = world_mats[i]
        # Alembic expects column-major 4x4; AbcGeom uses Imath.M44d (row/col order is API-specific)
        xform_sample = AbcGeom.XformSample()
        xform_sample.setMatrix(AbcGeom.M44d(*M.flatten().tolist()))
        xform_schema.set(xform_sample)

        cam_sample = AbcGeom.CameraSample()
        cam_schema.set(cam_sample)
```

Notes:
- The exact matrix class name may differ (some builds use `imath.M44d`).
- You must confirm row-major vs column-major for your binding and transpose if needed.
- UE import often expects centimeters; scale translation if your COLMAP units are meters.
