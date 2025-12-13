#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


API_LATEST = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/latest"
DEFAULT_ASSET = "ffmpeg-master-latest-win64-lgpl.zip"


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "cinetracker-dev"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    dest.write_bytes(_http_get(url))


def _copy_tree_files(src_dir: Path, dest_dir: Path, *, force: bool) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        if not f.is_file():
            continue
        dest = dest_dir / f.name
        if dest.exists() and not force:
            continue
        shutil.copy2(f, dest)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Download an FFmpeg Windows zip and extract ffmpeg.exe/ffprobe.exe into third_party/bin."
    )
    p.add_argument("--out-dir", default="third_party/src", help="Download/extract directory")
    p.add_argument("--bin-dir", default="third_party/bin", help="Where to place ffmpeg.exe/ffprobe.exe")
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

    print(f"Downloading FFmpeg {tag} asset: {args.asset_name}")
    _download(url, zip_path)
    print(f"Saved: {zip_path}")

    extract_dir = out_dir / f"ffmpeg-{tag}-windows"
    if args.force and extract_dir.exists():
        shutil.rmtree(extract_dir)
    if not extract_dir.exists():
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

    # Find the first "bin" dir containing ffmpeg.exe.
    bin_candidates = [p for p in extract_dir.rglob("bin") if (p / "ffmpeg.exe").exists()]
    if not bin_candidates:
        print(f"Could not find ffmpeg.exe in extracted archive: {extract_dir}", file=sys.stderr)
        return 2
    ff_bin = bin_candidates[0]

    # Copy ffmpeg.exe/ffprobe.exe and any adjacent DLLs from the bin dir.
    _copy_tree_files(ff_bin, bin_dir, force=args.force)

    for exe in ("ffmpeg.exe", "ffprobe.exe"):
        if not (bin_dir / exe).exists():
            print(f"Expected {exe} not found after install in: {bin_dir}", file=sys.stderr)
            return 2

    print(f"Installed to: {bin_dir / 'ffmpeg.exe'}")
    print("Tip: export FFMPEG_BIN to this path if needed:")
    print(f"  setx FFMPEG_BIN \"{(bin_dir / 'ffmpeg.exe').resolve()}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

