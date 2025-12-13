# S4.3 — User Acceptance Testing (UAT) Checklist

## Environment
- UE version is **5.7** (target) and required plugins are enabled (Camera Calibration/Lens Distortion, Alembic Importer, Sequencer).
- Windows build contains `Windows_CineTracker.exe` and bundled binaries in `_internal/third_party/bin`.

## Calibration Mode (F-01)
- Select chessboard video; run completes without UI freeze.
- Output includes `lens_calibration_data.json` with `camera_model=OPENCV` and keys: `fx, fy, cx, cy, k1, k2, p1, p2, image_width, image_height`.
- Values are consistent across repeated runs on the same input.

## Tracking Mode (F-02)
- Select scene video + calibration JSON; run completes without UI freeze.
- Intrinsics are frozen (verify `cameras.bin` matches injected OPENCV params).
- Output includes `camera_path.abc` with correct frame count/time base.

## Unreal Import
- Run `ue_scripts/s4_1_create_lens_file.py` to create Lens File asset; asset appears in Content Browser.
- Lens File is assigned to a CineCameraActor and viewport distortion matches footage (qualitative check).
- Import `camera_path.abc`; camera follows expected motion (forward/back + pan/tilt sanity test).
- Composure composite alignment is visually stable across the shot.

## Error Handling
- Missing binaries show actionable error message.
- Bad inputs (missing JSON / invalid video) show clear UI errors and do not crash.
