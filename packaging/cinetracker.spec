# PyInstaller spec (draft) for Cine-Tracker Windows build.
# Build example:
#   pyinstaller --clean --noconfirm packaging/cinetracker.spec

from __future__ import annotations

import os
import platform
from pathlib import Path

# NOTE: PyInstaller executes spec files in a custom namespace where `__file__`
# may not be defined. `SPECPATH` points to the directory containing this spec.
ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
ENTRY = SRC / "cinetracker" / "ui" / "main.py"

_sys = platform.system().lower()
_default_name = "CineTracker"
if _sys.startswith("windows"):
    _default_name = "Windows_CineTracker"
elif _sys.startswith("linux"):
    _default_name = "Linux_CineTracker"

APP_NAME = os.environ.get("CINETRACKER_APP_NAME", _default_name)

TP_BIN = ROOT / "third_party" / "bin"
COLMAP_EXE = TP_BIN / "colmap.exe"
FFMPEG_EXE = TP_BIN / "ffmpeg.exe"
FFPROBE_EXE = TP_BIN / "ffprobe.exe"


def _collect_colmap_files():
    if not COLMAP_EXE.exists():
        return []
    # Include colmap.exe + all adjacent DLLs it depends on (shipped in the release zip).
    items = [(str(COLMAP_EXE), "third_party/bin")]
    for p in COLMAP_EXE.parent.glob("*.dll"):
        items.append((str(p), "third_party/bin"))
    return items


def _collect_ffmpeg_files():
    items = []
    for exe in [FFMPEG_EXE, FFPROBE_EXE]:
        if exe.exists():
            items.append((str(exe), "third_party/bin"))
    for p in TP_BIN.glob("av*.dll"):
        items.append((str(p), "third_party/bin"))
    for p in TP_BIN.glob("sw*.dll"):
        items.append((str(p), "third_party/bin"))
    return items


datas = []
datas += _collect_colmap_files()
datas += _collect_ffmpeg_files()


block_cipher = None

a = Analysis(
    [str(ENTRY)],
    pathex=[str(ROOT), str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6", "numpy"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "pyinstaller_runtime_hook.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    strip=False,
    upx=False,
    name=APP_NAME,
)
