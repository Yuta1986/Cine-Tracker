# Sprint 2 Core Logic: S2.1 + S2.2

This doc provides the concrete code-level “contract” for:
- **S2.1** exporting `lens_calibration_data.json` in **OPENCV** schema (for UE lens import).
- **S2.2** injecting fixed intrinsics into `database.db` before running Tracking Mode (F-02).

---

## S2.1 — Intrinsic JSON Export (OPENCV)

### Requirement recap
The JSON must:
- Use **OPENCV** keys (`fx, fy, cx, cy, k1, k2, p1, p2`) even if some are zero.
- Include image resolution: `image_width`, `image_height`.

### Implementation
Use:
- `src/cinetracker/core/lens_json.py`

Example snippet:

```python
from cinetracker.core.lens_json import opencv_intrinsics_from_colmap_camera, write_lens_calibration_json

# Example: SIMPLE_RADIAL camera from S1.4 dummy test
model_name = "SIMPLE_RADIAL"
width, height = 3072, 2304
params = [2560.7, 1536.0, 1152.0, -0.0165322]  # f, cx, cy, k

intr = opencv_intrinsics_from_colmap_camera(model_name=model_name, width=width, height=height, params=params)
write_lens_calibration_json(intr.to_json_dict(), "output/lens_calibration_data.json")
```

Conversion policy when the COLMAP camera is not OPENCV:
- `SIMPLE_RADIAL(f,cx,cy,k)` → `OPENCV(fx=f, fy=f, cx, cy, k1=k, k2=0, p1=0, p2=0)`

---

## S2.2 — Fixed Parameter Injection (Tracking Mode)

### Method
Raw **SQLite** update (no PyCOLMAP required):
- `src/cinetracker/core/colmap_db.py` (updates `cameras` table `model/width/height/params`)

Wrapper for Sprint 2:
- `src/cinetracker/core/tracking_intrinsics.py`

Injection snippet:

```python
from cinetracker.core.tracking_intrinsics import inject_fixed_intrinsics_from_json

database_path = "path/to/database.db"
lens_json_path = "output/lens_calibration_data.json"

inject_fixed_intrinsics_from_json(
    database_path=database_path,
    lens_json_path=lens_json_path,
    camera_id=None,     # if DB has one camera, auto-select
    update_all=False,   # set True only if you know you have multiple camera rows
    dry_run=False,
)
```

### Mapper arguments to guarantee intrinsics are NEVER optimized
Pass these flags to `colmap mapper` during F-02:
- `--Mapper.ba_refine_focal_length 0`
- `--Mapper.ba_refine_principal_point 0`
- `--Mapper.ba_refine_extra_params 0`

Programmatic access:
- `cinetracker.core.tracking_intrinsics.recommended_tracking_mapper_args()`

