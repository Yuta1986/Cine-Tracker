#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

try:
    from cinetracker.core.colmap_db import inject_intrinsics_into_database
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if src_dir.is_dir():
        sys.path.insert(0, str(src_dir))
    from cinetracker.core.colmap_db import inject_intrinsics_into_database


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Inject fixed intrinsic camera parameters into a COLMAP SQLite database (database.db)."
    )
    parser.add_argument("--database", required=True, help="Path to COLMAP database.db")
    parser.add_argument("--json", required=True, help="Path to lens_calibration_data.json")
    parser.add_argument(
        "--camera-id",
        type=int,
        default=None,
        help="Camera ID to update (default: if exactly one camera exists, update it; else require --camera-id or --all).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all cameras in the DB (use with care; usually you want exactly one camera shared by all images).",
    )
    parser.add_argument("--model", default=None, help="Override JSON camera model (e.g., OPENCV).")
    parser.add_argument(
        "--set-dimensions",
        action="store_true",
        help="Also update camera width/height from JSON (requires image_width/image_height in JSON).",
    )
    parser.add_argument(
        "--no-prior-focal-length",
        action="store_true",
        help="Do not set prior_focal_length=1 (default: set it).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print changes but do not write.")
    args = parser.parse_args(argv)

    return inject_intrinsics_into_database(
        database_path=args.database,
        json_path=args.json,
        camera_id=args.camera_id,
        update_all=args.all,
        override_model=args.model,
        set_dimensions=args.set_dimensions,
        set_prior_focal_length=not args.no_prior_focal_length,
        dry_run=args.dry_run,
        out=sys.stdout,
        err=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
