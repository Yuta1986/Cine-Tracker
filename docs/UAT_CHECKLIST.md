# S4.3 — User Acceptance Testing (UAT) Checklist

## Environment
- UE version is **5.7** (target) and required plugins are enabled (Camera Calibration/Lens Distortion, Alembic Importer, Sequencer).
- Windows build contains `Windows_CineTracker.exe` and bundled binaries in `_internal/third_party/bin`.

## Capture Guide (for best results)

General (applies to both calibration + tracking):
- Use manual settings: lock focus, exposure, ISO, white balance; avoid auto-exposure flicker.
- Prefer minimal motion blur: higher shutter speed (e.g., 1/250–1/1000 depending on motion) and adequate lighting.
- Disable in-camera stabilization and rolling “HDR/auto” modes that change the image over time.
- Use high resolution + bitrate (avoid heavy compression); keep frame rate constant (CFR) if possible.
- Keep the lens fixed during a take: no zoom changes, no refocus pulls; avoid touching the focus/zoom ring mid-shot.

Calibration video (chessboard):
- Use a flat, rigid checkerboard with known square size; print large enough to fill a good portion of the frame.
- Record 30–90 seconds with the board visible most of the time; avoid fast motion and blur.
- Cover the full image: move the board to corners/edges and vary distance (near/mid/far) and tilt angles.
- Avoid reflections and glare; ensure even lighting and high contrast (sharp corners matter).

Tracking video (the scene):
- Ensure the scene has texture and features (posters, furniture, edges); avoid blank walls/flat surfaces.
- Add parallax: include small translation (dolly/side-step) instead of only panning in place.
- Avoid rapid whip-pans and strong motion blur; keep motion smooth.
- Avoid cuts and big occlusions; if possible start with 1–2 seconds static, then move.

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
