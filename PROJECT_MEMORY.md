# PROJECT_MEMORY.md - OSS Cine-Tracker Project Log

## 1. Project Goal & Scope
**Objective:** Create a Python/COLMAP desktop application for high-precision camera tracking optimized for Unreal Engine (UE) Composure.
**Core Modes:**
1.  **Calibration Mode (F-01):** Outputs `lens_calibration_data.json` (fixed intrinsics).
2.  **Tracking Mode (F-02):** Outputs `camera_path.abc` (extrinsics only, using fixed intrinsics).

## 2. Technical Constraints and Prerequisites
| Constraint | Status | Details |
| :--- | :--- | :--- |
| **Development Environment** | MANDATORY | Must operate within a **Virtual Environment** (`venv` or `conda`). |
| **Performance** | SATISFIED | CUDA-enabled COLMAP (Windows CUDA release) is installed at `third_party/bin/colmap.exe` and verified to report “with CUDA”. |
| **Core Tool** | Fixed | COLMAP (using the `OPENCV` camera model). |
| **Output Formats** | Fixed | Alembic (`.abc`) for path; JSON for lens parameters. |
| **UE Integration** | Target | Automatic import via UE Python scripts. |

## 3. Latest Decisions and Status
| Decision Point | Status | Details |
| :--- | :--- | :--- |
| **Sprint 1 Status** | Done | Sprint 1: Foundation & Core COLMAP Integration is Complete. |
| **Target Sprint** | In Progress | Sprint 3: GUI & Packaging. |
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
| **Next Action** | Pending | Execute **S3.1 / S3.2**: finalize PySide6 layout and wire non-blocking COLMAP pipeline execution + progress streaming. |
| **I/O Logic** | Defined | COLMAP poses ($T_{W \\to C}$) must be inverted for UE/Alembic ($T_{C \\to W}$). |

---
**END OF PROJECT MEMORY**
