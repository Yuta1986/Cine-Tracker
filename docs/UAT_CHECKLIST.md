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

## Windows Build UAT — Detailed Test Cases (F-01/F-02/S4.1)

### UAT-WIN-00 — Build Artifact Sanity
- Locate the built app:
  - Onedir: `dist\windows\onedir\Windows_CineTracker\Windows_CineTracker.exe`
  - Onefile: `dist\windows\onefile\Windows_CineTracker.exe`
- For onedir, confirm bundled binaries exist under `_internal\third_party\bin\`:
  - `colmap.exe`
  - `ffmpeg.exe`
  - `ffprobe.exe`
- Pass criteria: files exist and app launches on a clean Windows machine without installing COLMAP/FFmpeg system-wide.

### UAT-WIN-01 — Smoke Launch + Log Output
- Launch `Windows_CineTracker.exe`.
- Confirm the UI opens and shows the two panels: **F-01 Setup (Calibration)** and **F-02 Setup (Tracking)**.
- Click **Run F-01** and **Run F-02** with no inputs to confirm the app blocks with a clear error message (no crash).
- Pass criteria: no crash; errors are actionable (missing file paths).

### UAT-WIN-02 — F-01 Calibration Run (Checkerboard Video)
- Input: a checkerboard calibration video (30–90s) that covers corners/edges and near/far/tilt.
- Set **Output Dir** to an empty folder (e.g., `C:\CineTracker\UAT\f01_run1`).
- Run **F-01 (Calibration)**.
- Verify artifacts:
  - `lens_calibration_data.json` exists in the output directory.
  - JSON contains: `camera_model=OPENCV`, `fx,fy,cx,cy,k1,k2,p1,p2,image_width,image_height`.
  - `image_width`/`image_height` are non-zero and match the input video/frame size.
- Pass criteria: run completes without UI freeze; JSON is produced and parseable.

### UAT-WIN-03 — F-01 Repeatability (Same Input)
- Repeat UAT-WIN-02 to a second output folder (e.g., `...\f01_run2`) with the same input video.
- Compare the two `lens_calibration_data.json` files.
- Pass criteria: results are consistent (minor numerical differences acceptable; major deviations indicate instability).

### UAT-WIN-04 — F-02 Tracking Run (Scene Video + Fixed Intrinsics)
- Input: a tracking/scene video with texture + parallax and minimal blur.
- Input lens JSON: `lens_calibration_data.json` from UAT-WIN-02.
- Set **Output Dir** to an empty folder (e.g., `C:\CineTracker\UAT\f02_run1`).
- Run **F-02 (Tracking)**.
- Verify artifacts:
  - `camera_path.abc` exists and has non-trivial size.
  - Output contains COLMAP work products (e.g., `database.db`, `sparse\0\`), depending on pipeline settings.
- Pass criteria: run completes without UI freeze; Alembic is produced and non-empty.

### UAT-WIN-05 — Unreal Engine 5.7 Import (S4.1/S4.2)
- In UE 5.7, enable required plugins (Camera Calibration/Lens Distortion, Alembic Importer, Sequencer).
- Run `ue_scripts/s4_1_create_lens_file.py` using the UAT-WIN-02 `lens_calibration_data.json`.
- Run `ue_scripts/s4_2_import_alembic_and_bind.py` using the UAT-WIN-04 `camera_path.abc`.
- Pass criteria:
  - Lens File asset is created and assigned to the CineCameraActor.
  - Camera motion matches the footage qualitatively (no axis flips; translation direction makes sense).
  - Composure alignment is visually stable across the shot.

### UAT-WIN-06 — Negative Tests (Robustness)
- Missing/renamed bundled binaries:
  - Temporarily rename `_internal\third_party\bin\ffmpeg.exe` and run F-01/F-02.
  - Pass criteria: app fails gracefully with a clear message about missing FFmpeg (no crash).
- Invalid JSON:
  - Provide a non-OPENCV JSON or corrupt JSON to F-02.
  - Pass criteria: clear validation error (no crash).
