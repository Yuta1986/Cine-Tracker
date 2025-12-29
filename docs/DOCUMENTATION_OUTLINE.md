# S4.4 — Documentation Structure (Draft)

## 1. Overview
- What Cine-Tracker does (F-01 calibration + F-02 tracking for UE Composure).
- Release gating: baseline Windows UAT before merging F-04.

## 2. Installation
- Windows installer/zip contents.
- GPU driver/CUDA expectations.
- Included binaries (COLMAP/FFmpeg) and where they live in the install.

## 3. Quick Start
- Run F-01 on chessboard footage → produce `lens_calibration_data.json`
- Run F-02 on scene footage → produce `camera_path.abc`
- Import into UE using provided scripts.
- Run Windows UAT checklist: `docs/UAT_CHECKLIST.md`

## 4. Unreal Engine Integration
- Enabling required plugins.
- Running `ue_scripts/s4_1_create_lens_file.py`
- Running `ue_scripts/s4_2_import_alembic_and_bind.py`
- Assigning/validating Lens File + Sequencer tracks.

## 5. Hybrid Calibration (F-04) (Advanced / In-Development)
- High-level overview: no-checkerboard distortion solve (Plumb-Line + constrained BA).
- Native interface and array layout (Phase 3): `docs/F04_PHASE3_INTERFACE.md`
- Packaging considerations for native extension on Windows: `docs/PACKAGING_WINDOWS.md`

## 5. Troubleshooting
- “database is locked” on WSL/Windows pathing
- “COLMAP without CUDA” / GPU not used
- Alembic import doesn’t create camera track (version differences)

## 6. Roadmap
- UI polish, additional camera models, unit scaling, principal point offset handling.

## 7. Licensing
- Project license (e.g., MIT/Apache-2.0) — to be chosen.
- Third-party licenses:
  - COLMAP (license + attribution)
  - FFmpeg (license + build type)
  - Any Python dependencies
