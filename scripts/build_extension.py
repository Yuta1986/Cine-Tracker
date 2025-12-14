#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _find_artifact(build_dir: Path) -> Path:
    system = platform.system().lower()
    exts = [".pyd"] if system == "windows" else [".so", ".dylib"]
    candidates: list[Path] = []
    for ext in exts:
        candidates.extend(build_dir.rglob(f"cinetracker_native*{ext}"))
    if not candidates:
        raise FileNotFoundError("Built module not found under build directory.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Cine-Tracker native extension (pybind11 + Ceres) via CMake."
    )
    parser.add_argument("--build-dir", default="native/build", help="CMake build directory")
    parser.add_argument("--config", default="Release", help="Build config (Release/Debug)")
    parser.add_argument("--install-to", default="src", help="Directory to copy the built module into")
    parser.add_argument("--python", default=sys.executable, help="Python executable to bind against")
    parser.add_argument(
        "--vcpkg-root",
        default=os.environ.get("VCPKG_ROOT", ""),
        help="Path to vcpkg root (or set VCPKG_ROOT)",
    )
    parser.add_argument(
        "--triplet",
        default=os.environ.get("VCPKG_TARGET_TRIPLET", "x64-windows-static-md"),
        help="vcpkg triplet (Windows only)",
    )
    parser.add_argument(
        "--optional",
        action="store_true",
        help="If required build tools are missing, exit 0 instead of failing",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    source_dir = repo_root / "native"
    build_dir = repo_root / args.build_dir
    install_to = (repo_root / args.install_to).resolve()
    python_exe = Path(args.python)

    if not source_dir.exists():
        raise FileNotFoundError(f"native/ not found at: {source_dir}")

    if shutil.which("cmake") is None:
        msg = "cmake not found on PATH."
        if args.optional:
            print(f"[build_extension] SKIP: {msg}")
            return 0
        print(f"[build_extension] ERROR: {msg}", file=sys.stderr)
        return 2

    system = platform.system().lower()
    if system == "windows":
        if not os.environ.get("VSINSTALLDIR"):
            print(
                "[build_extension] NOTE: VSINSTALLDIR is not set. If you hit build errors, run this from the\n"
                "                  'Developer Command Prompt for VS 2022' (or after running vcvars64.bat)."
            )
        if shutil.which("cl") is None:
            msg = (
                "MSVC cl.exe not found on PATH. Run from a Developer Command Prompt, "
                "or ensure MSVC environment vars are set."
            )
            if args.optional:
                print(f"[build_extension] SKIP: {msg}")
                return 0
            print(f"[build_extension] ERROR: {msg}", file=sys.stderr)
            return 2

    build_dir.mkdir(parents=True, exist_ok=True)
    install_to.mkdir(parents=True, exist_ok=True)

    cmake_configure = [
        "cmake",
        "-S",
        str(source_dir),
        "-B",
        str(build_dir),
        f"-DPython_EXECUTABLE={python_exe}",
    ]

    if system == "windows":
        vcpkg_root = Path(args.vcpkg_root) if args.vcpkg_root else None
        if vcpkg_root:
            toolchain = vcpkg_root / "scripts" / "buildsystems" / "vcpkg.cmake"
            if toolchain.exists():
                cmake_configure.extend(
                    [
                        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
                        f"-DVCPKG_TARGET_TRIPLET={args.triplet}",
                    ]
                )

    if system != "windows":
        cmake_configure.append(f"-DCMAKE_BUILD_TYPE={args.config}")

    print("[build_extension] Configure:", " ".join(cmake_configure))
    _run(cmake_configure)

    cmake_build = ["cmake", "--build", str(build_dir)]
    if system == "windows":
        cmake_build.extend(["--config", args.config])
    else:
        cmake_build.extend(["-j", str(os.cpu_count() or 1)])

    print("[build_extension] Build:", " ".join(cmake_build))
    _run(cmake_build)

    artifact = _find_artifact(build_dir)
    dest = install_to / artifact.name
    shutil.copy2(artifact, dest)
    print(f"[build_extension] Installed: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
