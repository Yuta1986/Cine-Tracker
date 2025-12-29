# Sprint 3 — Windows Packaging Plan (PyInstaller)

For a user-facing “how to build/run” guide (devs vs testers vs packagers), see: `docs/BUILDING.md`.

Target: ship a standalone Windows executable bundling:
- Python + our `cinetracker` package
- External binaries: `colmap.exe` (+ required DLLs) and `ffmpeg.exe` (+ DLLs if needed)
 - (Future F-04) optional native extension: `cinetracker_native.pyd` (Ceres + pybind11)

## Proposed packaged directory layout

When built with PyInstaller (one-folder mode):

```
CineTracker/
  Windows_CineTracker.exe
  _internal/
    cinetracker/                (our python package)
    PySide6/                    (Qt)
    numpy/                      (core deps)
    third_party/
      bin/
        colmap.exe
        *.dll                    (all DLLs shipped with COLMAP release)
        ffmpeg.exe
        ffprobe.exe
```

Runtime resolution policy:
- The app sets `COLMAP_BIN` and `FFMPEG_BIN` to the bundled `_internal/third_party/bin/*` at startup.
  - Implementation: `cinetracker.runtime.configure_bundled_binaries()` (also used as a PyInstaller runtime hook).

## Notes
- COLMAP Windows CUDA release ships `colmap.exe` and a set of DLLs that must be placed adjacent to it.
- FFmpeg Windows builds may be static or may require DLLs; bundle them similarly.

## Automated fetching
The Windows build helper can download the required external binaries into `third_party/bin`:
- COLMAP: `scripts/fetch_colmap_windows_cuda.py` (invoked by `build_windows.bat --fetch-colmap`)
- FFmpeg: `scripts/fetch_ffmpeg_windows.py` (invoked by `build_windows.bat --fetch-ffmpeg`)

## (F-04) Native extension build (optional)
If you want to build and bundle the native Ceres/pybind11 extension:
- Run the build from **Developer Command Prompt for VS 2022** (MSVC toolchain on PATH).
- Recommended vcpkg triplet for Python CRT compatibility: `x64-windows-static-md`.
  - Set `VCPKG_ROOT` and (optionally) `VCPKG_TARGET_TRIPLET=x64-windows-static-md`.
- Build via the Windows helper:
  - `build_windows.bat --build-native --fetch-colmap --fetch-ffmpeg`

Notes:
- `--build-native` calls `scripts/build_extension.py` which configures CMake for `native/` and copies `cinetracker_native.pyd` into `src/` prior to packaging.
