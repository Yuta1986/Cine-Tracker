# S1.5 — COLMAP Binary Data Structures (NumPy Arrays)

This doc finalizes the Sprint 1 I/O data structures we will use going into Sprint 2.

## 1) Loading camera poses into NumPy arrays (qvec / tvec)

`images.bin` stores per-image pose as:
- `qvec` (4 floats): quaternion **world→camera** rotation in COLMAP order **(qw, qx, qy, qz)**
- `tvec` (3 floats): translation for **world→camera** transform

### Code snippet (N images → (N,4) and (N,3))

```python
import numpy as np
from cinetracker.core.colmap_binary_reader import COLMAPBinaryReader

model_dir = "/path/to/sparse/0"
r = COLMAPBinaryReader(model_dir)

# Stable ordering; N=20 for the S1.4 dummy test run
poses = r.read_pose_arrays(order_by="image_id")

qvecs: np.ndarray = poses.qvecs  # shape (N,4)
tvecs: np.ndarray = poses.tvecs  # shape (N,3)

assert qvecs.shape[1] == 4
assert tvecs.shape[1] == 3
```

## 2) Loading point cloud coordinates into a NumPy array

```python
pc = r.read_pointcloud_arrays()
xyz: np.ndarray = pc.xyz  # shape (M,3)
rgb: np.ndarray = pc.rgb  # shape (M,3)
```

## 3) Intrinsics: SIMPLE_RADIAL → OPENCV for JSON

Project memory mandates using `OPENCV` for the final `lens_calibration_data.json`.

For the S1.4 dummy test, the first camera was `SIMPLE_RADIAL` with parameters:
- `f, cx, cy, k`

Conversion policy (used only when the model is not already OPENCV):
- `fx = fy = f`
- `cx = cx`, `cy = cy`
- `k1 = k`, `k2 = 0`
- `p1 = 0`, `p2 = 0`

Implementation helper: `src/cinetracker/core/colmap_binary_reader.py`

