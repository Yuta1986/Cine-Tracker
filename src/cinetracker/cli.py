from __future__ import annotations

import argparse
import sys

from cinetracker.core.colmap_db import inject_intrinsics_into_database


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cinetracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    doc = sub.add_parser("doctor", help="Check environment (binaries + dependency versions)")
    doc.add_argument("--full-freeze", action="store_true", help="Also print full `pip freeze` output")
    doc.add_argument("--colmap-bin", default=None, help="Explicit path to COLMAP binary (or set COLMAP_BIN)")
    doc.add_argument("--ffmpeg-bin", default=None, help="Explicit path to FFmpeg binary (or set FFMPEG_BIN)")
    doc.add_argument(
        "--check-gpu",
        action="store_true",
        help="Also check if COLMAP exposes GPU flags and whether NVIDIA tooling is present",
    )

    inj = sub.add_parser("inject-intrinsics", help="Inject fixed intrinsics into COLMAP database.db")
    inj.add_argument("--database", required=True, help="Path to COLMAP database.db")
    inj.add_argument("--json", required=True, help="Path to lens_calibration_data.json")
    inj.add_argument("--camera-id", type=int, default=None, help="Camera ID to update")
    inj.add_argument("--all", action="store_true", help="Update all cameras")
    inj.add_argument("--model", default=None, help="Override JSON camera model (e.g., OPENCV)")
    inj.add_argument("--set-dimensions", action="store_true", help="Also set width/height from JSON")
    inj.add_argument("--no-prior-focal-length", action="store_true", help="Do not set prior_focal_length=1")
    inj.add_argument("--dry-run", action="store_true", help="Print changes but do not write")

    insp = sub.add_parser("inspect-model", help="Inspect COLMAP model files (cameras.bin/images.bin/points3D.bin)")
    insp.add_argument("--model", required=True, help="Path to COLMAP model directory (e.g., sparse/0)")
    insp.add_argument("--limit", type=int, default=1, help="How many cameras/images to preview")

    t1 = sub.add_parser("s1-sfm-test", help="Sprint 1 basic SfM test (downloads sample dataset and runs mapper)")
    t1.add_argument("--workdir", default="output/s1_sfm_test", help="Output working directory")
    t1.add_argument(
        "--dataset-url",
        default=None,
        help="Override dataset zip URL (default: South Building sample from COLMAP releases)",
    )
    t1.add_argument("--force", action="store_true", help="Force re-download and re-extract dataset")
    t1.add_argument("--colmap-bin", default=None, help="Explicit path to COLMAP binary (or set COLMAP_BIN)")
    t1.add_argument("--max-images", type=int, default=30, help="Limit images for faster dummy test (0 = all)")

    f02 = sub.add_parser("s2-validate-f02", help="S2.3: Validate fixed-intrinsics tracking run (F-02)")
    f02.add_argument("--workdir", required=True, help="Working directory (recommend a Windows path under /mnt/c for colmap.exe)")
    f02.add_argument("--max-images", type=int, default=50, help="Limit images for faster validation (0 = all)")
    f02.add_argument("--colmap-bin", default=None, help="Explicit path to COLMAP binary (or set COLMAP_BIN)")

    gui = sub.add_parser("gui", help="Start the PySide6 GUI")

    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        from cinetracker.core.doctor import run_doctor

        return run_doctor(
            full_freeze=args.full_freeze,
            colmap_bin=args.colmap_bin,
            ffmpeg_bin=args.ffmpeg_bin,
            check_gpu=args.check_gpu,
            out=sys.stdout,
            err=sys.stderr,
        )

    if args.cmd == "inject-intrinsics":
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

    if args.cmd == "inspect-model":
        from cinetracker.core.model_inspect import inspect_model

        return inspect_model(model_dir=args.model, limit=args.limit, out=sys.stdout, err=sys.stderr)

    if args.cmd == "s1-sfm-test":
        from cinetracker.core.s1_sfm_test import DEFAULT_SOUTH_BUILDING_URL, run_basic_sfm_test

        return run_basic_sfm_test(
            work_dir=args.workdir,
            dataset_url=args.dataset_url or DEFAULT_SOUTH_BUILDING_URL,
            force_redownload=args.force,
            max_images=args.max_images,
            colmap_bin=args.colmap_bin,
            out=sys.stdout,
            err=sys.stderr,
        )

    if args.cmd == "s2-validate-f02":
        from cinetracker.core.s2_validate_f02 import run_f02_validation

        return run_f02_validation(
            work_dir=args.workdir,
            max_images=args.max_images,
            colmap_bin=args.colmap_bin,
            out=sys.stdout,
            err=sys.stderr,
        )

    if args.cmd == "gui":
        from cinetracker.ui.main import main as gui_main

        return gui_main()

    parser.error(f"Unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
