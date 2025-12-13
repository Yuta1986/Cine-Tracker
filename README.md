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
