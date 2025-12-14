# Building & Running (By Audience)

This repo supports two common workflows:
- **Run from source (developers)**: you install Python deps in a venv and run `cinetracker` / `cinetracker-gui`.
- **Windows packaged app (testers/end users)**: you run `Windows_CineTracker.exe` produced by the PyInstaller build.

## 1) Windows end users / UAT testers (no Python)

### What you need
- A Windows build folder or exe:
  - Onedir: `dist\windows\onedir\Windows_CineTracker\Windows_CineTracker.exe`
  - Onefile: `dist\windows\onefile\Windows_CineTracker.exe`
- If Windows reports missing runtime DLLs like `MSVCP140.dll` / `VCRUNTIME140.dll`:
  - Install **Microsoft Visual C++ Redistributable for Visual Studio 2015–2022 (x64)**.

### Run
- Double-click `Windows_CineTracker.exe`, or launch it from a terminal if you want to see console output.
- UAT checklist: `docs/UAT_CHECKLIST.md`

## 2) Developers (Windows / macOS / Linux / WSL)

### Prereqs
- Python **3.10+**
- External tools:
  - `ffmpeg` and `colmap` on `PATH`, or set explicit paths:
    - `FFMPEG_BIN=/absolute/path/to/ffmpeg`
    - `COLMAP_BIN=/absolute/path/to/colmap`

### Setup (one-time per machine)
- Create venv: `python -m venv .venv`
- Activate:
  - Linux/macOS/WSL: `. .venv/bin/activate`
  - Windows PowerShell: `.\.venv\Scripts\Activate.ps1`
- Install deps (dev-from-source): `python -m pip install -U pip setuptools wheel`
- Install project (editable): `python -m pip install -e ".[core,ui,io]"`

### Run
- GUI (recommended): `cinetracker gui` or `cinetracker-gui`
- CLI help: `cinetracker --help`
- Environment check: `cinetracker doctor --check-gpu`

## 3) Windows packagers (build the .exe with PyInstaller)

Windows executables must be built on Windows (PyInstaller does not cross-compile).

### Prereqs
- Python **3.10+** installed and available as `python` in `cmd.exe`
- If you plan to build the optional native extension (`--build-native`):
  - Visual Studio 2022 / Build Tools, and ideally run from **Developer Command Prompt for VS 2022**

### Guided build (beginner-friendly)
- Recommended shortcut (reliable): `build_windows_quick.bat`
- Optional interactive menu (prompts): `build_windows.bat --menu --pause`
- `build_windows_easy.bat` is kept as a deprecated alias that forwards to `build_windows_quick.bat`.

### Non-interactive build (good for CI / power users)
- Recommended shortcut (no menu): `build_windows_quick.bat`
- Or run directly:
- Build both outputs (recommended): `build_windows.bat --fetch-colmap --fetch-ffmpeg`
- Build onedir only: `build_windows.bat --onedir --fetch-colmap --fetch-ffmpeg`
- Build onefile only: `build_windows.bat --onefile --fetch-colmap --fetch-ffmpeg`

### Notes
- Avoid running from `\\wsl.localhost\...` as the current directory in CMD (UNC paths can fail). If needed, start CMD normally and `pushd` into the repo folder.
- If the guided menu fails in your shell environment, use `build_windows_quick.bat` (no interactive prompts) or run `build_windows.bat ...` directly.
- Outputs:
  - Onedir: `dist\windows\onedir\Windows_CineTracker\Windows_CineTracker.exe`
  - Onefile: `dist\windows\onefile\Windows_CineTracker.exe`

## 4) macOS / Linux “end-user builds”

This repo currently documents and supports **Windows** packaging via PyInstaller.

- On macOS/Linux, use the **developer** workflow (“run from source”) above.
- If you choose to experiment with PyInstaller on macOS/Linux, treat it as unsupported and validate thoroughly (paths/bundled binaries differ by OS).
