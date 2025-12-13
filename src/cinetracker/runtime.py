from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedBinaries:
    third_party_bin: Path | None
    colmap_bin: Path | None
    ffmpeg_bin: Path | None


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))

    try:
        roots.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    # PyInstaller onedir commonly uses an internal dir adjacent to the exe.
    if roots:
        roots.append(roots[-1] / "_internal")

    # Fallback: project-relative
    roots.append(Path.cwd())
    return [r for r in roots if r is not None]


def _find_third_party_bin(root: Path) -> Path | None:
    # Prefer the packaged layout: <root>/third_party/bin
    p = root / "third_party" / "bin"
    if p.is_dir():
        return p
    return None


def resolve_bundled_binaries() -> ResolvedBinaries:
    for root in _candidate_roots():
        tp = _find_third_party_bin(root)
        if not tp:
            continue
        colmap = next((tp / n for n in ("colmap.exe", "colmap") if (tp / n).exists()), None)
        ffmpeg = next((tp / n for n in ("ffmpeg.exe", "ffmpeg") if (tp / n).exists()), None)
        return ResolvedBinaries(third_party_bin=tp, colmap_bin=colmap, ffmpeg_bin=ffmpeg)
    return ResolvedBinaries(third_party_bin=None, colmap_bin=None, ffmpeg_bin=None)


def configure_bundled_binaries(*, strict: bool = False) -> ResolvedBinaries:
    """
    Runtime bootstrap for packaged apps:
    - Look for bundled `third_party/bin` near the executable (PyInstaller).
    - Set `COLMAP_BIN` / `FFMPEG_BIN` so subprocess calls work without user PATH setup.
    """

    resolved = resolve_bundled_binaries()

    if resolved.colmap_bin and not os.environ.get("COLMAP_BIN"):
        os.environ["COLMAP_BIN"] = str(resolved.colmap_bin)
    if resolved.ffmpeg_bin and not os.environ.get("FFMPEG_BIN"):
        os.environ["FFMPEG_BIN"] = str(resolved.ffmpeg_bin)

    if strict and (resolved.colmap_bin is None or resolved.ffmpeg_bin is None):
        missing = []
        if resolved.colmap_bin is None:
            missing.append("colmap")
        if resolved.ffmpeg_bin is None:
            missing.append("ffmpeg")
        raise RuntimeError(f"Missing bundled binaries: {', '.join(missing)}")

    return resolved

