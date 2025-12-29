#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main(argv: list[str]) -> int:
    if platform.system().lower() != "windows":
        print("ERROR: Windows packaging must be run on Windows.", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]

    p = argparse.ArgumentParser(description="Windows build helper (Python driver for PyInstaller).")
    p.add_argument("--fetch-colmap", action="store_true", help="Download COLMAP Windows CUDA build into third_party/bin")
    p.add_argument("--fetch-ffmpeg", action="store_true", help="Download FFmpeg Windows build into third_party/bin")
    p.add_argument("--force", action="store_true", help="Redownload/overwrite when fetching binaries")
    p.add_argument("--build-native", action="store_true", help="Build optional native extension before packaging")
    p.add_argument("--onedir", action="store_true", help="Build folder-based app only")
    p.add_argument("--onefile", action="store_true", help="Build single-file exe only")
    p.add_argument("--out", default=r"dist\windows", help=r"Output folder root (default: dist\windows)")
    args = p.parse_args(argv)

    mode = "both"
    if args.onedir and args.onefile:
        mode = "both"
    elif args.onedir:
        mode = "onedir"
    elif args.onefile:
        mode = "onefile"

    venv_dir = root / ".venv-win"
    venv_py = venv_dir / "Scripts" / "python.exe"
    if not venv_py.exists():
        print(f"Creating virtual environment: {venv_dir}")
        _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=root)

    print("Upgrading packaging tools...")
    _run([str(venv_py), "-m", "pip", "install", "-U", "pip", "setuptools", "wheel"], cwd=root)

    print("Installing project + dependencies...")
    _run([str(venv_py), "-m", "pip", "install", "-e", ".[core,ui,io]"], cwd=root)

    print("Installing PyInstaller...")
    _run([str(venv_py), "-m", "pip", "install", "-U", "pyinstaller"], cwd=root)

    if args.build_native:
        print("Building native extension (cinetracker_native)...")
        cmd = [str(venv_py), str(root / "scripts" / "build_extension.py"), "--config", "Release", "--install-to", "src"]
        vcpkg_root = os.environ.get("VCPKG_ROOT")
        if vcpkg_root:
            cmd += ["--vcpkg-root", vcpkg_root]
        _run(cmd, cwd=root)

    if args.fetch_colmap:
        print("Fetching COLMAP Windows CUDA binary into third_party\\bin ...")
        cmd = [str(venv_py), str(root / "scripts" / "fetch_colmap_windows_cuda.py")]
        if args.force:
            cmd.append("--force")
        _run(cmd, cwd=root)

    if args.fetch_ffmpeg:
        print("Fetching FFmpeg Windows build into third_party\\bin ...")
        cmd = [str(venv_py), str(root / "scripts" / "fetch_ffmpeg_windows.py")]
        if args.force:
            cmd.append("--force")
        _run(cmd, cwd=root)

    out_dir = Path(args.out)
    app_name = os.environ.get("CINETRACKER_APP_NAME", "Windows_CineTracker")

    if mode in ("onedir", "both"):
        print("Building (onedir) with PyInstaller...")
        _run(
            [
                str(venv_py),
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                "--distpath",
                str(out_dir / "onedir"),
                "--workpath",
                str(root / "build" / "pyinstaller" / "onedir"),
                str(root / "packaging" / "cinetracker.spec"),
            ],
            cwd=root,
        )

    if mode in ("onefile", "both"):
        print("Building (onefile) with PyInstaller...")
        _run(
            [
                str(venv_py),
                "-m",
                "PyInstaller",
                "--clean",
                "--noconfirm",
                "--distpath",
                str(out_dir / "onefile"),
                "--workpath",
                str(root / "build" / "pyinstaller" / "onefile"),
                str(root / "packaging" / "cinetracker_onefile.spec"),
            ],
            cwd=root,
        )

    print()
    print("Build complete:")
    if mode in ("onedir", "both"):
        print(rf"  Onedir:  {out_dir}\onedir\{app_name}\{app_name}.exe")
    if mode in ("onefile", "both"):
        print(rf"  Onefile: {out_dir}\onefile\{app_name}.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

