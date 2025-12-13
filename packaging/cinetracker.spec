# PyInstaller spec (draft) for Cine-Tracker Windows build.
# Build example:
#   pyinstaller --clean --noconfirm packaging/cinetracker.spec

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ENTRY = SRC / "cinetracker" / "ui" / "main.py"

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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CineTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
