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
    inj_json = inj.add_mutually_exclusive_group(required=True)
    inj_json.add_argument("--json", help="Path to lens_calibration_data.json")
    inj_json.add_argument("--profile", help="Lens profile name (see `cinetracker profile list`)")
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

    f04 = sub.add_parser(
        "f04-plumbline-refine",
        help="F-04 prototype: refine k1/k2 using 2D plumb-line constraints (requires native Ceres extension)",
    )
    f04.add_argument("--images", required=True, help="Directory containing extracted frames/images")
    f04.add_argument("--lens-json", required=True, help="Input lens_calibration_data.json (OPENCV)")
    f04.add_argument("--out-json", required=True, help="Output lens_calibration_data.json (updated k1/k2)")
    f04.add_argument("--max-images", type=int, default=30, help="Limit images for faster runs (0 = all)")
    f04.add_argument("--max-lines-per-image", type=int, default=200, help="Max LSD segments per image")
    f04.add_argument("--min-line-length", type=float, default=120.0, help="Minimum line length in pixels")
    f04.add_argument("--sample-step", type=float, default=8.0, help="Sample step along line segments in pixels")
    f04.add_argument("--outer-iters", type=int, default=6, help="Outer iterations (fit lines -> Ceres step)")
    f04.add_argument(
        "--median-reproj-px",
        type=float,
        default=1.0,
        help="Approx median reprojection error in pixels (used to scale lambda_line)",
    )
    f04.add_argument("--lambda-cap", type=float, default=5.0, help="Max lambda_line")
    f04.add_argument("--cauchy-scale", type=float, default=2.0, help="Cauchy robust loss scale in pixels")

    gui = sub.add_parser("gui", help="Start the PySide6 GUI")

    prof = sub.add_parser("profile", help="Manage reusable lens profiles (saved lens_calibration_data.json)")
    prof_sub = prof.add_subparsers(dest="profile_cmd", required=True)

    prof_add = prof_sub.add_parser("add", help="Save a lens calibration JSON as a named profile")
    prof_add.add_argument("--name", required=True, help="Profile name (used as filename)")
    prof_add.add_argument("--json", required=True, help="Path to lens_calibration_data.json")
    prof_add.add_argument("--overwrite", action="store_true", help="Overwrite if profile exists")

    prof_list = prof_sub.add_parser("list", help="List saved profiles")
    prof_list.add_argument("--verbose", action="store_true", help="Show more details")

    prof_path = prof_sub.add_parser("path", help="Print the profile JSON path")
    prof_path.add_argument("--name", required=True)

    prof_rm = prof_sub.add_parser("remove", help="Remove a profile")
    prof_rm.add_argument("--name", required=True)

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
        json_path = args.json
        if not json_path and getattr(args, "profile", None):
            from cinetracker.core.lens_profiles import resolve_profile_json

            json_path = str(resolve_profile_json(args.profile))
        return inject_intrinsics_into_database(
            database_path=args.database,
            json_path=json_path,
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

    if args.cmd == "f04-plumbline-refine":
        from cinetracker.core.colmap_db import load_intrinsics_spec
        from cinetracker.core.f04_plumbline import build_plumbline_input_from_images, refine_k1k2_plumbline_only
        from cinetracker.core.lens_json import write_lens_calibration_json

        spec = load_intrinsics_spec(args.lens_json, override_model="OPENCV")
        if spec.image_width is None or spec.image_height is None:
            print("lens-json must include image_width and image_height for F-04.", file=sys.stderr)
            return 2
        need = ["fx", "fy", "cx", "cy", "k1", "k2"]
        missing = [k for k in need if k not in spec.params_by_name]
        if missing:
            print(f"lens-json missing required keys: {', '.join(missing)}", file=sys.stderr)
            return 2

        pl = build_plumbline_input_from_images(
            images_dir=args.images,
            fx=spec.params_by_name["fx"],
            fy=spec.params_by_name["fy"],
            cx=spec.params_by_name["cx"],
            cy=spec.params_by_name["cy"],
            k1=spec.params_by_name["k1"],
            k2=spec.params_by_name["k2"],
            max_images=args.max_images,
            max_lines_per_image=args.max_lines_per_image,
            min_line_length_px=args.min_line_length,
            sample_step_px=args.sample_step,
            out=sys.stdout,
        )

        k1, k2, metrics = refine_k1k2_plumbline_only(
            pl,
            outer_iters=args.outer_iters,
            median_reproj_px=args.median_reproj_px,
            lambda_cap=args.lambda_cap,
            cauchy_scale_px=args.cauchy_scale,
            out=sys.stdout,
        )

        out_dict = {
            "version": 1,
            "camera_model": "OPENCV",
            "image_width": int(spec.image_width),
            "image_height": int(spec.image_height),
            "fx": float(spec.params_by_name["fx"]),
            "fy": float(spec.params_by_name["fy"]),
            "cx": float(spec.params_by_name["cx"]),
            "cy": float(spec.params_by_name["cy"]),
            "k1": float(k1),
            "k2": float(k2),
            "p1": float(spec.params_by_name.get("p1", 0.0)),
            "p2": float(spec.params_by_name.get("p2", 0.0)),
            "f04_plumbline": {
                "outer_iters": int(args.outer_iters),
                "cauchy_scale_px": float(args.cauchy_scale),
                "lambda_cap": float(args.lambda_cap),
                "median_reproj_px": float(args.median_reproj_px),
                "num_samples": int(pl.sample_uv.shape[0]),
                "num_lines": int(pl.num_lines),
                "metrics": [
                    {
                        "outer_iter": int(m.outer_iter),
                        "k1": float(m.k1),
                        "k2": float(m.k2),
                        "median_line_px": float(m.median_line_px),
                        "lambda_line": float(m.lambda_line),
                    }
                    for m in metrics
                ],
            },
        }
        write_lens_calibration_json(out_dict, args.out_json)
        print(f"[f04] wrote: {args.out_json}")
        return 0

    if args.cmd == "gui":
        from cinetracker.ui.main import main as gui_main

        return gui_main()

    if args.cmd == "profile":
        from cinetracker.core.lens_profiles import add_profile, list_profiles, remove_profile, resolve_profile_json

        if args.profile_cmd == "add":
            try:
                p = add_profile(name=args.name, json_path=args.json, overwrite=args.overwrite)
            except Exception as e:
                print(f"Failed to add profile: {e}", file=sys.stderr)
                return 2
            print(f"Saved profile: {args.name} -> {p}")
            return 0

        if args.profile_cmd == "list":
            profiles = list_profiles()
            if not profiles:
                print("No profiles found.")
                return 0
            for prof in profiles:
                if args.verbose:
                    dims = (
                        f"{prof.image_width}x{prof.image_height}"
                        if prof.image_width is not None and prof.image_height is not None
                        else "?"
                    )
                    model = prof.camera_model or "?"
                    created = prof.created_at or "?"
                    disp = prof.display_name or prof.name
                    print(f"{prof.name}\t{disp}\t{model}\t{dims}\t{created}")
                else:
                    print(prof.name)
            return 0

        if args.profile_cmd == "path":
            try:
                print(resolve_profile_json(args.name))
            except Exception as e:
                print(str(e), file=sys.stderr)
                return 2
            return 0

        if args.profile_cmd == "remove":
            try:
                remove_profile(name=args.name)
            except Exception as e:
                print(f"Failed to remove profile: {e}", file=sys.stderr)
                return 2
            print(f"Removed profile: {args.name}")
            return 0

        parser.error(f"Unknown profile command: {args.profile_cmd}")
        return 2

    parser.error(f"Unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
