# PROJECT_MEMORY.md - OSS Cine-Tracker Project Log

Single source of truth: update this file at the end of each work session and when closing a sprint.
Legacy alias `Project memory.md` is kept as a pointer for convenience.

## 0. Session & Sprint Log (always update)
Add an entry here at the end of each work session (and when closing a sprint) so progress is easy to audit.

**Template (copy/paste):**
- **Session YYYY-MM-DD** (Sprint X)
  - Changes:
  - Decisions:
  - Next:
  - Blockers:

**Log:**
- **Session 2025-12-14 (Latest)** (Sprint 4 / F-04 Specification & Build)
  - Changes: Confirmed full F-04 specification (Plumb-Line constraint, Ceres backend). Created dedicated feature branch. FFmpeg bundling added and verified.
  - Decisions: Windows build (`build_windows.bat --fetch-colmap --fetch-ffmpeg`) successful and ready for UAT. F-04 implementation deferred to feature branch (`feature/f-04-hybrid-calib`).
  - Next: Execute UAT Checklist on the successfully built Windows `.exe` to validate F-01/F-02/S4.1 functionality. Concurrently, start S4.5/S4.6 implementation on the F-04 feature branch (WSL).
  - Blockers: None.
- **Session 2025-12-14 (Cont.)** (Sprint 4 / F-04 Refinement)
  - Changes: Finalized F-04 output schema extension and optimization scope to prevent ambiguity during UAT and downstream integration.
  - Decisions: Reuse standard `lens_calibration_data.json` OPENCV keys and add mandatory `f04_metadata` with confidence/fit metrics. Define F-04 optimization as staged joint BA (ending in full joint constrained BA with strong priors on weak parameters).
  - Next: Keep UAT as the gate for shipping F-01/F-02/S4.1; implement S4.5/S4.6 on `feature/f-04-hybrid-calib` in parallel.
  - Blockers: None.
- **Session 2025-12-14 (Cont.)** (Sprint 4 / F-04 Build + UAT Hardening)
  - Changes: Added detailed Windows UAT test cases; added `scripts/build_extension.py` and wired `build_windows.bat --build-native` for the Ceres/pybind11 module; added VS environment visibility guidance (`VSINSTALLDIR`).
  - Decisions: Prefer `vcpkg` triplet `x64-windows-static-md` for Python CRT compatibility when producing `cinetracker_native.pyd`.
  - Next: Run Windows UAT (F-01/F-02/S4.1) using `docs/UAT_CHECKLIST.md`; begin native extension environment setup + incremental F-04 implementation on `feature/f-04-hybrid-calib`.
  - Blockers: None.
- **Session 2025-12-14 (Cont.)** (Sprint 4 / F-04 WSL Native Build)
  - Changes: Installed WSL build prerequisites (CMake/Ninja, `pybind11-dev`, `libceres-dev`, `python3.12-dev`); built `cinetracker_native` successfully via `python scripts/build_extension.py`; fixed a native segfault caused by Ceres loss-function ownership (double-free) by setting `loss_function_ownership=DO_NOT_TAKE_OWNERSHIP`.
  - Decisions: Keep both pybind overloads for `plumbline_refine_k1k2` (legacy scalar args + new array-based bridge signature) for compatibility and incremental migration.
  - Next: Implement the next F-04 native blocks on `feature/f-04-hybrid-calib` (priors + staged unlocks); add a real-data regression test for the Phase-1 refine pipeline.
  - Blockers: None.
- **Session 2025-12-14** (Sprint 4 / Post-implementation)
  - Changes: Added a session/sprint log section and standardized project memory to a single canonical file with a compatibility pointer.
  - Decisions: Treat `PROJECT_MEMORY.md` as the canonical project memory file.
  - Next: Keep this log updated every session/sprint; run UE 5.7 UAT and Windows build when ready.
  - Blockers: None in-repo; UE validation requires running Unreal Engine.

## 1. Project Goal & Scope
**Objective:** Create a Python/COLMAP desktop application for high-precision camera tracking optimized for Unreal Engine (UE) Composure.
**Core Modes:**
1.  **Calibration Mode (F-01):** Outputs `lens_calibration_data.json` (fixed intrinsics; checkerboard required).
2.  **Tracking Mode (F-02):** Outputs `camera_path.abc` (extrinsics only, using fixed intrinsics).
3.  **Hybrid Calibration Mode (F-04):** Outputs `lens_calibration_data.json` with checkerboard-free distortion estimates from general scene footage (F-04 always emits `f04_metadata`; downstream must treat it as optional for backward compatibility).

## 2. Technical Constraints and Prerequisites
| Constraint | Status | Details |
| :--- | :--- | :--- |
| **Development Environment** | MANDATORY | Must operate within a **Virtual Environment** (`venv` or `conda`). |
| **Performance** | SATISFIED | CUDA-enabled COLMAP (Windows CUDA release) is installed at `third_party/bin/colmap.exe` and verified to report “with CUDA”. |
| **Core Tool** | Fixed | COLMAP (using the `OPENCV` camera model). |
| **Output Formats** | Fixed | Alembic (`.abc`) for path; JSON for lens parameters. |
| **UE Integration** | Target | Automatic import via UE Python scripts. |
| **F-04 Backend** | Defined (Deferred) | Requires a custom **Ceres Solver** C++ extension (via **pybind11**) for performance/robustness (Windows DLL build via MSVC); developed on `feature/f-04-hybrid-calib` and not yet integrated into mainline. |

## 3. Latest Decisions and Status
| Decision Point | Status | Details |
| :--- | :--- | :--- |
| **Sprint 1 Status** | Done | Sprint 1: Foundation & Core COLMAP Integration is Complete. |
| **Sprint 3 Status** | Done | Sprint 3: GUI & Packaging is Complete. |
| **Sprint 4 Status** | Done (implementation) | Sprint 4: UE Integration & Final Testing scripts/docs are implemented; final validation requires human UAT inside UE 5.7. |
| **Target Sprint** | Done | All Sprints (1–4) are complete (implementation complete; pending human UAT). |
| **Completed (this repo)** | Done | `.venv` created; core CLI seeded (`cinetracker`); `cinetracker doctor` added; local user-space binaries bootstrapped via `scripts/bootstrap_binaries_linux.sh`. |
| **Environment (S1.1)** | Done | Work is in `.venv` and verified via `sys.prefix != sys.base_prefix`. |
| **Binary Resolution (S1.1)** | Done | `ffmpeg` and CUDA-enabled `colmap.exe` are callable via `subprocess.run()` using `third_party/bin/*` fallback or `COLMAP_BIN` / `FFMPEG_BIN`. |
| **CUDA Requirement (S1.2/S1.3)** | Done | Installed COLMAP Windows CUDA build (`third_party/bin/colmap.exe`); `cinetracker doctor --check-gpu` confirms “with CUDA” and GPU flags are present. |
| **S1.4 (SfM Dummy Test)** | Done | Test run on 20-image subset of South Building dataset; output model created and parsed. Header counts: `cameras.bin=1`, `images.bin=20`, `points3D.bin=4506`. First camera: `model=SIMPLE_RADIAL`, `size=3072x2304`, `params=[f=2560.7, cx=1536, cy=1152, k=-0.0165322]`. |
| **S1.5 (Binary Reader Structures)** | Done | Added `COLMAPBinaryReader` helpers for `(N,4)` qvec and `(N,3)` tvec arrays + point cloud arrays; documented SIMPLE_RADIAL→OPENCV parameter mapping for JSON. |
| **S2.1 (OPENCV JSON Export)** | Done | Implemented canonical `lens_calibration_data.json` builder with full OPENCV keys + `image_width/image_height` (zeros filled when needed). |
| **S2.2 (Fixed Intrinsics Injection)** | Done | Uses raw SQLite update of COLMAP `database.db` (`cameras` table) and provides fixed-intrinsics mapper args: `--Mapper.ba_refine_focal_length 0 --Mapper.ba_refine_principal_point 0 --Mapper.ba_refine_extra_params 0`. |
| **S2.3 (Fixed Intrinsics Validation)** | Done | Ran F-02 validation on 50 images with injected OPENCV intrinsics; output `cameras.bin` matches injected params exactly (max abs diff 0.0). |
| **S2.4 (Alembic + UE Basis)** | Done (code/design) | Implemented pose inversion (`T_{W→C}`→`T_{C→W}`) and a fixed `M_{COLMAP→UE}` basis transform; documented PyAlembic writing calls for time-sampled world matrices. |
| **S2.4 Basis Matrix** | Defined | `M_{COLMAP→UE} = [[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]]` mapping OpenCV/COLMAP camera axes (x right, y down, z forward) to UE world axes (X right, Y forward, Z up). |
| **Completed (S3.1/S3.2)** | Done | PySide6 UI skeleton + QThread signal/slot worker for non-blocking subprocess execution + log/progress streaming. |
| **Completed (S3.3/S3.4)** | Done | Packaging plan + PyInstaller spec + runtime bootstrap that sets `COLMAP_BIN` / `FFMPEG_BIN` from bundled `third_party/bin` at startup. |
| **I/O Logic** | Defined | COLMAP poses ($T_{W \\to C}$) must be inverted for UE/Alembic ($T_{C \\to W}$). |
| **S4.1 (UE Lens File Script)** | Implemented (needs UE run) | Added UE Python script to create a LensFile asset from `lens_calibration_data.json` and populate Brown-Conrady distortion where public API exists. |
| **S4.2 (UE Alembic Import/Bind Script)** | Implemented (needs UE run) | Added UE Python script to import Alembic, create/find CineCameraActor, assign LensFile, and bind actor to a Level Sequence (Alembic-to-camera track creation is UE-version dependent). |
| **S4.3 (UAT Checklist)** | Drafted | Added UAT checklist for end-to-end validation in UE 5.7. |
| **S4.4 (Docs Outline)** | Drafted | Added documentation outline including licensing + troubleshooting sections. |
| **README Licensing Section** | Done | Added licensing/attribution section naming COLMAP (The Structure-from-Motion Software) and FFmpeg and other key dependencies. |
| **PyInstaller Build (Linux)** | Done | Ran `pyinstaller --clean packaging/cinetracker.spec`; produced `dist/cinetracker` (Linux ELF). |
| **Windows Build (PyInstaller)** | Done (Ready for UAT) | Windows build succeeded using `build_windows.bat --fetch-colmap --fetch-ffmpeg` and FFmpeg bundling was verified; execute UAT on the built `.exe`. |
| **F-04 Hybrid Calibration** | In-Progress (Deferred) | Major new feature: checkerboard-free distortion estimation via constrained bundle adjustment regularized by a Plumb-Line constraint; staged joint BA is required; implementation isolated on `feature/f-04-hybrid-calib` due to native dependency + stability risks. |
| **Next Action** | UAT + Parallel Dev | Run UE 5.7 UAT on the Windows build for F-01/F-02/S4.1; in parallel, implement S4.5/S4.6 for F-04 on `feature/f-04-hybrid-calib` (WSL). |

## 4. F-04 Feature Development (Deferred/In-Progress)
| Decision Point | Status | Details |
| :--- | :--- | :--- |
| **F-04: Hybrid Calibration** | In-Progress (Branch) | **Checkerboard-free distortion estimation** from general footage; implemented on `feature/f-04-hybrid-calib` to avoid regressions in F-01/F-02. |
| **F-04 Core Method** | Defined | Constrained bundle adjustment (joint optimization) regularized by the **Plumb-Line Constraint** derived from detected 2D line segments. Reprojection error remains in the cost function to anchor the solution to 3D structure. |
| **F-04 Backend** | Defined (Deferred) | Custom **Ceres Solver** C++ extension via **pybind11** for performance/robustness; requires cross-platform native builds (Windows DLL via MSVC). |
| **F-04 Optimization Scope** | Defined | **Staged Joint BA** with incremental unlock: Phase 1 optimize `K1,K2` only; Phase 2 optimize `K1,K2,P1,P2` + intrinsics (`fx,fy,cx,cy`) while holding poses/points; Phase 3 optimize distortion + intrinsics + poses + 3D points (full joint constrained BA). Final delivery runs **Phase 3** with strong priors/damping on weak parameters (`P1,P2,cx,cy`). |
| **F-04 Output Schema** | Defined | Reuse the standard `lens_calibration_data.json` OPENCV keys for intrinsics/distortion. When generated by F-04, add `f04_metadata` with fit-quality metrics: `confidence_score` (0.0–1.0), `median_plumb_line_residual_px`, `line_count`. |
| **F-04 Confidence Metric** | Defined | `confidence_score` is `S_conf = C_spatial * exp(-α * E_median)`, where `C_spatial` is 8×8 grid coverage (fraction of cells containing ≥1 line sample), `E_median` is `median_plumb_line_residual_px`, and `α = -ln(0.9) ≈ 0.10536` so `E_median=1.0px` at `C_spatial=1.0` yields `S_conf≈0.9`. UAT thresholds: Pass `≥0.7`, Warning `[0.4,0.7)`, Reject `<0.4`. |
| **F-04 Optimization Priors** | Defined | Phase 3 uses Ceres NormalPriors to prevent degeneracy: `cx,cy` prior to image center with `σx=0.02*W`, `σy=0.02*H`; tangential `P1,P2` prior 0 with `σ=1e-6`; radial `K1,K2` prior to Phase-2 result with `σ=1e-3`. |
| **JSON Compatibility** | Defined | Downstream consumers must use a try-get pattern for `f04_metadata`. If `f04_metadata` is missing, treat calibration as **F-01 reference grade** with implicit confidence `1.0` (backward-compatible). |
| **Build/CI Strategy** | Defined | Windows toolchain: MSVC 2022 + `vcpkg`. Build a static-linked `cinetracker_native.pyd` (Ceres deps statically linked to reduce DLL issues) and integrate into `build_windows.bat` via `--build-native` (calls `scripts/build_extension.py`, which checks for `cl.exe` and drives the `pybind11` build). |
| **S4.5/S4.6 Status** | In Development | Implement the `pybind11` ⇄ Ceres data bridge and plumb-line residual cost function + robust loss; implement `f04_metadata` computation and thresholding; then integrate into a CLI/UI workflow guarded by `S_conf` thresholds. |

---
**END OF PROJECT MEMORY**
