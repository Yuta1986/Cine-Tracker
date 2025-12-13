# Cine-Tracker

## Virtual environment (required)

Development outside a virtual environment is not supported.

Create and activate a local venv named `.venv`:
- Create: `python3 -m venv .venv`
- Activate (Linux/macOS/WSL): `. .venv/bin/activate`
- Activate (Windows PowerShell): `.\.venv\Scripts\Activate.ps1`

Install dependencies into this venv:
- Upgrade tooling: `python -m pip install -U pip setuptools wheel`
- Install project (editable): `python -m pip install -e .`
- Install core deps: `python -m pip install numpy PySide6`

Verify you are inside the venv:
- `python -c "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"`

Configure external binaries (required):
- Ensure `ffmpeg` and `colmap` are installed and on `PATH`, or set explicit paths:
  - `export FFMPEG_BIN=/absolute/path/to/ffmpeg`
  - `export COLMAP_BIN=/absolute/path/to/colmap`
  - (Windows) set `FFMPEG_BIN` / `COLMAP_BIN` in System Environment Variables

Binary call test (what the core module uses):
- `python -c "import subprocess; subprocess.run(['ffmpeg','-version'], check=True)"`
- `python -c "import subprocess; subprocess.run(['colmap','-h'], check=True)"`

Local dev seeds:
- Install (editable): `python3 -m pip install -e .`
- Intrinsics injection into COLMAP `database.db`: `cinetracker inject-intrinsics --database path/to/database.db --json lens_calibration_data.json --dry-run`
- Environment check (binaries + versions): `cinetracker doctor --check-gpu`
- Inspect COLMAP outputs: `cinetracker inspect-model --model path/to/sparse/0`

## Lens profiles (reuse calibration)

Save a calibration JSON once, then reuse it by name:
- Save: `cinetracker profile add --name "MyLens_24mm_f2.8" --json path\\to\\lens_calibration_data.json`
- List: `cinetracker profile list --verbose`
- Use with injection: `cinetracker inject-intrinsics --database path\\to\\database.db --profile "MyLens_24mm_f2.8"`

## Windows build (PyInstaller)

Windows executables must be built on Windows (PyInstaller does not cross-compile).

Note: don’t run `build_windows.bat` from `\\wsl.localhost\...` as the current directory (CMD prints “UNC paths are not supported”). If needed, start CMD normally and use `pushd` into the repo first.

From a Windows terminal in the repo root:
- Build both outputs (optionally fetch COLMAP): `build_windows.bat --fetch-colmap`
- Build both outputs (no downloads): `build_windows.bat`
- Build folder-based app only (faster startup): `build_windows.bat --onedir`
- Build single-file exe only (all-in-one): `build_windows.bat --onefile`
- Choose output folder in Explorer: `build_windows.bat --choose-dist`
- Explicit output folder: `build_windows.bat --distpath "D:\\Apps\\CineTracker" --fetch-colmap`

Windows builds use a separate venv folder: `.venv-win` (so it doesn’t conflict with the Linux/WSL `.venv`).

Output:
- Windows (onedir): `dist\\windows\\onedir\\Windows_CineTracker\\Windows_CineTracker.exe`
- Windows (onefile): `dist\\windows\\onefile\\Windows_CineTracker.exe`
- Linux (if you run PyInstaller on Linux): `dist\\linux\\Linux_CineTracker\\Linux_CineTracker` (no `.exe`)

Override the output name (optional):
- Set `CINETRACKER_APP_NAME` before running PyInstaller (or `build_windows.bat`).

## Licensing and attributions

This project incorporates and/or interoperates with the following third‑party software. Their license terms must be respected:

- **COLMAP (The Structure-from-Motion Software)** — BSD 3‑Clause License. Source: https://github.com/colmap/colmap
- **FFmpeg** — licensed under LGPL v2.1 or later, with optional GPL components depending on how FFmpeg is built. Site: https://ffmpeg.org/
- **PySide6 / Qt for Python (Qt)** — LGPL v3. Source: https://www.qt.io/qt-for-python
- **NumPy** — BSD 3‑Clause License. Source: https://numpy.org/
- **PyInstaller** (packaging) — GPL with an exception for distributing bundled applications. Source: https://pyinstaller.org/

Notes:
- If you redistribute this application with bundled binaries (e.g., `colmap.exe`, `ffmpeg.exe`), you must also redistribute the corresponding license notices and comply with each license’s distribution requirements (e.g., LGPL/GPL obligations for FFmpeg builds).
