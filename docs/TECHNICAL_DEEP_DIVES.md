# Technical Deep Dives (Sprint 2 Risks)

This doc resolves the open technical questions in the Sprint plan:
- **S2.2 Parameter Injection** (fixed intrinsics in COLMAP)
- **S2.4 Alembic Conversion** (pose + coordinate conversion)
- **S4.1 UE Lens File creation** (OpenCV → UE lens model)

---

## 1) COLMAP Fixed Intrinsics Injection (S2.2)

### Decision: Prefer SQLite injection (no PyCOLMAP required)

For **Tracking Mode (F-02)**, the most robust/portable way to force fixed intrinsics is:
1. **Write camera intrinsics into `database.db`** (SQLite `cameras` table).
2. **Run `colmap mapper` with bundle-adjustment refinement disabled for intrinsics**.

This avoids:
- Compiling `pycolmap` (often the biggest setup risk on Windows/macOS).
- Editing `cameras.bin`/`images.bin` (which is not what the mapper reads as input anyway).

PyCOLMAP is still useful later for convenience reading models, but is not required to solve S2.2.

### What COLMAP actually reads for intrinsics

During reconstruction, COLMAP reads the camera model + parameters from the **SQLite database**:
- Table: `cameras`
- Columns (typical COLMAP schema):
  - `camera_id` (INTEGER)
  - `model` (INTEGER enum)
  - `width` / `height` (INTEGER)
  - `params` (BLOB of little-endian float64)
  - `prior_focal_length` (INTEGER, 0/1)

The `params` field is just packed doubles in the same order as the camera model definition.

### Camera model parameter ordering (what we must write)

For the common case used in the spec:

**`OPENCV`** (8 params):
1. `fx`
2. `fy`
3. `cx`
4. `cy`
5. `k1`
6. `k2`
7. `p1`
8. `p2`

Other models exist (e.g., `PINHOLE`, `SIMPLE_PINHOLE`, `FULL_OPENCV`), but Sprint 2 can scope to `OPENCV` first.

### Bundle adjustment flags to keep intrinsics fixed

To ensure COLMAP does not change intrinsics during mapping, set:
- `--Mapper.ba_refine_focal_length 0`
- `--Mapper.ba_refine_principal_point 0`
- `--Mapper.ba_refine_extra_params 0`

This is the “make it stick” half of fixed intrinsics. Injecting the DB alone is not enough if refinement is enabled.

### Recommended JSON structure (lens_calibration_data.json)

Keep it explicit and versionable:

```json
{
  "version": 1,
  "camera_model": "OPENCV",
  "image_width": 1920,
  "image_height": 1080,
  "fx": 1234.5,
  "fy": 1230.1,
  "cx": 960.0,
  "cy": 540.0,
  "k1": -0.01,
  "k2": 0.002,
  "p1": 0.0001,
  "p2": -0.0002
}
```

### Implementation

Use `scripts/colmap_inject_intrinsics.py` to update `database.db` in-place.

---

## 2) COLMAP → Alembic pose conversion (S2.4)

### COLMAP pose convention (from images.bin)

COLMAP stores for each image a rotation `R` and translation `t` such that:

`X_cam = R * X_world + t`  (world → camera)

Therefore:
- Camera-to-world rotation: `R_c2w = R^T`
- Camera center in world coordinates: `C = -R^T * t`

The camera-to-world transform matrix is:

```
T_c2w = [ R^T  C ]
        [ 0    1 ]
```

### Unreal coordinate convention note (needs explicit validation)

Unreal is **left-handed** with **X forward, Y right, Z up**.
OpenCV camera coordinates are typically **right-handed** with **x right, y down, z forward**.

A common axis remap from OpenCV camera coords → UE camera coords is:
- `X_ue = Z_cv`
- `Y_ue = X_cv`
- `Z_ue = -Y_cv`

Matrix form (acts on 3-vectors):

```
S = [ 0  0  1 ]
    [ 1  0  0 ]
    [ 0 -1  0 ]
```

If `T_c2w_colmap` is expressed in the COLMAP world basis, then expressing the *same* transform in UE basis is typically:

`T_c2w_ue = S4 * T_c2w_colmap * S4^{-1}`  (with `S4 = diag(S, 1)`)

Important: whether you need **only** this basis swap, or an additional world-frame alignment (e.g., “Z-up”) depends on how you want COLMAP’s arbitrary world to land in UE. Treat `S` as a starting point and validate on a known motion (e.g., forward dolly + yaw).

---

## 3) UE Lens File creation (S4.1)

### Distortion parameter mapping

If COLMAP uses `OPENCV`:
- `k1` → `K1`
- `k2` → `K2`
- `p1` → `P1`
- `p2` → `P2`

### Focal length conversion (pixels → mm)

UE CineCamera typically wants focal length in mm plus sensor size (filmback).

If you know the sensor width in mm (`sensor_width_mm`) and the image width in pixels (`image_width_px`):
- `focal_length_mm = fx_px * sensor_width_mm / image_width_px`

Similarly, for height:
- `focal_length_mm_from_fy = fy_px * sensor_height_mm / image_height_px`

In practice:
- Prefer using the **real sensor/filmback** dimensions for the device/lens (or a chosen “virtual filmback” that you keep consistent).
- Expect small mismatch between fx/fy if the pixel aspect ratio or scaling differs; choose a consistent policy (e.g., compute focal from `fx` and set sensor width + aspect).

### Principal point (cx, cy)

Unreal’s camera components don’t directly expose a “principal point in pixels” knob in the same way as OpenCV.
If you need principal point offsets, you generally represent them as **lens shift / optical center offset** (depending on the specific UE camera calibration pipeline you use). This should be validated against the UE `LensFile` / distortion pipeline in Sprint 4 once the exact API calls are confirmed.

