# Native Extension (F-04 / Ceres)

This folder builds the `cinetracker_native` Python extension module (pybind11 + Ceres).

The initial scope is **plumb-line-only distortion refinement** for `k1,k2`:
- `cinetracker_native.plumbline_refine_k1k2(...)`

## Windows build (MSVC + vcpkg)

Prereqs:
- Visual Studio 2022 (MSVC, x64)
- CMake 3.20+
- Python 3.10+ (same one you use for packaging / `.venv-win`)
- vcpkg (recommended)

Example (PowerShell, from repo root):

```powershell
# One-time: set up vcpkg and install deps
git clone https://github.com/microsoft/vcpkg.git C:\vcpkg
& C:\vcpkg\bootstrap-vcpkg.bat
& C:\vcpkg\vcpkg.exe install ceres pybind11 eigen3 --triplet x64-windows

# Configure + build
cmake -S native -B native\build `
  -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake `
  -DVCPKG_TARGET_TRIPLET=x64-windows `
  -DPython_EXECUTABLE=.\.venv-win\Scripts\python.exe

cmake --build native\build --config Release
```

The built artifact is `cinetracker_native.pyd` (location depends on generator/config). Make it importable by the Python environment used to run Cine-Tracker (e.g., copy next to `src/` during dev, or install into the `.venv-win` site-packages).

## Linux/WSL build (optional, for dev only)

If you have system Ceres + pybind11 installed:

```bash
cmake -S native -B native/build
cmake --build native/build -j
```
