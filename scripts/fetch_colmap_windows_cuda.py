#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


API_LATEST = "https://api.github.com/repos/colmap/colmap/releases/latest"
DEFAULT_ASSET = "colmap-x64-windows-cuda.zip"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cinetracker-dev"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    data = _http_get(url)
    dest.write_bytes(data)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Download latest COLMAP Windows CUDA zip and extract colmap.exe into third_party/bin.")
    p.add_argument("--out-dir", default="third_party/src", help="Download directory")
    p.add_argument("--bin-dir", default="third_party/bin", help="Where to place colmap.exe and its DLLs")
    p.add_argument("--asset-name", default=DEFAULT_ASSET, help="Release asset name to fetch")
    p.add_argument("--force", action="store_true", help="Redownload and overwrite extracted files")
    args = p.parse_args(argv)

    out_dir = Path(args.out_dir)
    bin_dir = Path(args.bin_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)

    raw = _http_get(API_LATEST)
    release = json.loads(raw.decode("utf-8"))
    tag = release.get("tag_name") or "unknown"
    assets = release.get("assets") or []

    asset = next((a for a in assets if a.get("name") == args.asset_name), None)
    if not asset:
        names = ", ".join(a.get("name", "?") for a in assets)
        print(f"Asset {args.asset_name!r} not found in latest release {tag}. Assets: {names}", file=sys.stderr)
        return 2

    url = asset.get("browser_download_url")
    if not url:
        print("No browser_download_url found for asset.", file=sys.stderr)
        return 2

    zip_path = out_dir / args.asset_name
    if args.force and zip_path.exists():
        zip_path.unlink()

    print(f"Downloading COLMAP {tag} asset: {args.asset_name}")
    _download(url, zip_path)
    print(f"Saved: {zip_path}")

    # Extract into a temp dir then copy relevant binaries into bin_dir so they are adjacent (DLL lookup).
    extract_dir = out_dir / f"colmap-{tag}-windows-cuda"
    if args.force and extract_dir.exists():
        shutil.rmtree(extract_dir)
    if not extract_dir.exists():
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

    # Find colmap.exe inside the extracted tree.
    exe_candidates = list(extract_dir.rglob("colmap.exe"))
    if not exe_candidates:
        exe_candidates = list(extract_dir.rglob("COLMAP.exe"))
    if not exe_candidates:
        print(f"Could not find colmap.exe in extracted archive: {extract_dir}", file=sys.stderr)
        return 2

    colmap_exe = exe_candidates[0]
    print(f"Found: {colmap_exe}")

    # Copy all files in the same directory as colmap.exe (exe + dlls) into bin_dir.
    src_dir = colmap_exe.parent
    for f in src_dir.iterdir():
        if f.is_file():
            dest = bin_dir / f.name
            if dest.exists() and not args.force:
                continue
            shutil.copy2(f, dest)

    # Ensure executable bit for WSL interop convenience.
    target_exe = bin_dir / colmap_exe.name
    try:
        mode = target_exe.stat().st_mode
        target_exe.chmod(mode | 0o111)
    except Exception:
        pass

    print(f"Installed to: {target_exe}")
    print("Tip: export COLMAP_BIN to this path if needed:")
    print(f"  export COLMAP_BIN=\"{target_exe.resolve()}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

