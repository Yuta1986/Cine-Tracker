# S4.3 — User Acceptance Testing (UAT) Checklist

This document is written for beginner developers running the **Windows baseline UAT** (F-01/F-02 + UE import).

## Beginner Quickstart (Recommended Order)
1. Run **UAT-WIN-00** to confirm the build folder is complete.
2. Run **UAT-WIN-01** to confirm the app launches and errors are friendly.
3. Run **UAT-WIN-02** and **UAT-WIN-03** to validate F-01 calibration + repeatability.
4. Run **UAT-WIN-04** to validate F-02 tracking output.
5. Run **UAT-WIN-05** inside UE 5.7 to validate import/binding.
6. Run **UAT-WIN-06** negative tests (robustness).

## What You Need
- Windows machine with Unreal Engine **5.7** installed.
- The built Cine-Tracker app:
  - Preferred (onedir): `dist\\windows\\onedir\\Windows_CineTracker\\Windows_CineTracker.exe`
  - Or (onefile): `dist\\windows\\onefile\\Windows_CineTracker.exe`
- Two videos:
  - Calibration (checkerboard) video for **F-01**
  - Tracking/scene video for **F-02**

## Environment (Required)
- UE version is **5.7** (target).
- Enable UE plugins:
  - Camera Calibration / Lens Distortion
  - Alembic Importer
  - Sequencer
- Windows build contains `Windows_CineTracker.exe` and bundled binaries in `_internal\\third_party\\bin`.

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

## Windows Build UAT — Test Cases (F-01/F-02/S4.1)

For each test case, record:
- Result: PASS / FAIL
- Evidence: output folder path + any app log text (copy/paste) + screenshots (optional)

### UAT-WIN-00 — Build Artifact Sanity
Goal: confirm the packaged executable and bundled binaries are present.

Steps:
- Locate the built app:
  - Onedir: `dist\\windows\\onedir\\Windows_CineTracker\\Windows_CineTracker.exe`
  - Onefile: `dist\\windows\\onefile\\Windows_CineTracker.exe`
- For onedir builds, confirm bundled binaries exist under `_internal\\third_party\\bin\\`:
  - `colmap.exe`, `ffmpeg.exe`, `ffprobe.exe`
- Launch `Windows_CineTracker.exe`.

Pass criteria:
- App launches without requiring system-wide COLMAP/FFmpeg installs.

### UAT-WIN-01 — Smoke Launch + Log Output
Goal: confirm basic UI and error handling.

Steps:
- Launch `Windows_CineTracker.exe`.
- Confirm the UI shows:
  - **F-01 Setup (Calibration)**
  - **F-02 Setup (Tracking)**
- Click **Run F-01** with no inputs.
- Click **Run F-02** with no inputs.

Pass criteria:
- No crash; errors are actionable (e.g., missing file path).

### UAT-WIN-02 — F-01 Calibration Run (Checkerboard Video)
Goal: generate a valid `lens_calibration_data.json` from checkerboard footage.

Steps:
- Set **F-01 Video** to a checkerboard calibration video (30–90s).
- Set **F-01 Output Dir** to an empty folder (example): `C:\\CineTracker\\UAT\\f01_run1`
- Click **Run F-01 (Calibration)**.

Verify:
- `lens_calibration_data.json` exists in the output dir.
- JSON contains:
  - `camera_model: "OPENCV"`
  - `fx, fy, cx, cy, k1, k2, p1, p2`
  - `image_width`, `image_height` (non-zero)

Pass criteria:
- Run completes without UI freeze; JSON is produced and parseable.

### UAT-WIN-03 — F-01 Repeatability (Same Input)
Goal: confirm calibration stability.

Steps:
- Repeat UAT-WIN-02 using the same input video to another empty folder (example): `C:\\CineTracker\\UAT\\f01_run2`
- Compare the two `lens_calibration_data.json` files.

Pass criteria:
- Results are consistent (minor numerical differences acceptable; large deviations are a FAIL).

### UAT-WIN-04 — F-02 Tracking Run (Scene Video + Fixed Intrinsics)
Goal: generate `camera_path.abc` using fixed intrinsics.

Steps:
- Set **F-02 Video** to a tracking/scene video (texture + parallax, minimal blur).
- Set **F-02 Lens JSON** to the `lens_calibration_data.json` from UAT-WIN-02.
- Set **F-02 Output Dir** to an empty folder (example): `C:\\CineTracker\\UAT\\f02_run1`
- Click **Run F-02 (Tracking)**.

Verify:
- `camera_path.abc` exists and has non-trivial size.

Pass criteria:
- Run completes without UI freeze; Alembic is produced and non-empty.

### UAT-WIN-05 — Unreal Engine 5.7 Import (S4.1/S4.2)
Goal: validate UE integration on the baseline build.

Steps (in UE 5.7):
- Ensure required plugins are enabled (Camera Calibration/Lens Distortion, Alembic Importer, Sequencer).
- Run `ue_scripts/s4_1_create_lens_file.py` using the UAT-WIN-02 `lens_calibration_data.json`.
- Run `ue_scripts/s4_2_import_alembic_and_bind.py` using the UAT-WIN-04 `camera_path.abc`.

Pass criteria:
- Lens File asset is created and assigned to a CineCameraActor.
- Camera motion matches footage qualitatively (no mirroring/axis flips; translation direction makes sense).
- Composure alignment is visually stable across the shot.

### UAT-WIN-06 — Negative Tests (Robustness)
Goal: confirm failure modes are safe and actionable.

Steps:
- Missing bundled binaries:
  - Temporarily rename `_internal\\third_party\\bin\\ffmpeg.exe`
  - Run F-01 or F-02 again.
- Invalid JSON:
  - Provide a corrupt JSON or non-OPENCV JSON to F-02.

Pass criteria:
- Clear error messages; no crash; app remains usable after the error.
