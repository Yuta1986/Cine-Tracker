from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import TextIO

from cinetracker.core.colmap_cli import COLMAP
from cinetracker.core.colmap_db import load_intrinsics_spec
from cinetracker.core.lens_json import opencv_intrinsics_from_colmap_camera, write_lens_calibration_json
from cinetracker.core.model_inspect import inspect_model
from cinetracker.core.tracking_intrinsics import FixedIntrinsicsMapperArgs


DATASET_URL = "https://github.com/colmap/colmap/releases/download/3.11.1/south-building.zip"


def _download(url: str, dest: Path, out: TextIO) -> None:
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"Using cached download: {dest}", file=out)
        return
    print(f"Downloading: {url}", file=out)
    with urllib.request.urlopen(url) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def _extract_zip(zip_path: Path, dest_dir: Path, *, expected_path: Path, out: TextIO) -> None:
    if expected_path.exists():
        print(f"Using existing extracted dataset: {dest_dir}", file=out)
        return
    print(f"Extracting: {zip_path} -> {dest_dir}", file=out)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def _to_camera_params_csv(intr_json_path: Path) -> str:
    spec = load_intrinsics_spec(intr_json_path, override_model="OPENCV")
    params = spec.params_in_colmap_order()
    return ",".join(f"{v:.12g}" for v in params)


def run_f02_validation(
    *,
    work_dir: str | Path,
    max_images: int,
    colmap_bin: str | None,
    out: TextIO,
    err: TextIO,
) -> int:
    """
    S2.3 validation run:
    - Build a fresh database from images
    - Export an OPENCV intrinsics JSON (as if from F-01)
    - Inject intrinsics into database.db (S2.2)
    - Run mapper with intrinsics refinement disabled
    - Confirm output cameras.bin matches injected params exactly (within float tolerance)
    """

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)

    dataset_zip = root / "south-building.zip"
    dataset_dir = root / "south-building"
    source_images = dataset_dir / "images"
    work_images = root / "images"
    db_path = root / "database.db"
    sparse_out = root / "sparse"
    model_out = sparse_out / "0"
    lens_json = root / "lens_calibration_data.json"

    _download(DATASET_URL, dataset_zip, out)
    _extract_zip(dataset_zip, root, expected_path=source_images, out=out)

    if not source_images.exists():
        print(f"Missing images dir: {source_images}", file=err)
        return 1

    # Use the Sprint 1 dummy intrinsics as our "calibration" baseline (SIMPLE_RADIAL → OPENCV policy).
    # These match the S1.4 recorded values.
    intr = opencv_intrinsics_from_colmap_camera(
        model_name="SIMPLE_RADIAL",
        width=3072,
        height=2304,
        params=[2560.7, 1536.0, 1152.0, -0.0165322],
    )
    write_lens_calibration_json(intr.to_json_dict(), lens_json)
    camera_params_csv = _to_camera_params_csv(lens_json)

    # Fresh workspace.
    if db_path.exists():
        db_path.unlink()
    if work_images.exists():
        shutil.rmtree(work_images)
    if sparse_out.exists():
        shutil.rmtree(sparse_out)
    work_images.mkdir(parents=True, exist_ok=True)

    images = sorted([p for p in source_images.iterdir() if p.is_file()])
    if max_images > 0:
        images = images[:max_images]
    print(f"Copying {len(images)} images into: {work_images}", file=out)
    for p in images:
        shutil.copy2(p, work_images / p.name)

    colmap = COLMAP.resolve(explicit=colmap_bin)
    print(f"Using COLMAP: {colmap.path}", file=out)

    # Detect GPU flag naming (3.13+ uses FeatureExtraction/FeatureMatching).
    fe_help = colmap.run(["feature_extractor", "-h"], timeout_s=20).stdout.lower()
    use_feature_gpu = "featureextraction.use_gpu" in fe_help
    use_sift_gpu = "siftextraction.use_gpu" in fe_help

    print("Running: colmap feature_extractor (OPENCV + fixed params) ...", file=out)
    fe_cmd = [
        "feature_extractor",
        "--database_path",
        str(db_path),
        "--image_path",
        str(work_images),
        "--ImageReader.single_camera",
        "1",
        "--ImageReader.camera_model",
        "OPENCV",
        "--ImageReader.camera_params",
        camera_params_csv,
    ]
    if use_feature_gpu:
        fe_cmd += ["--FeatureExtraction.use_gpu", "1", "--FeatureExtraction.gpu_index", "-1"]
    elif use_sift_gpu:
        fe_cmd += ["--SiftExtraction.use_gpu", "1", "--SiftExtraction.gpu_index", "-1"]
    fe_proc = colmap.run(fe_cmd, timeout_s=None)
    print(fe_proc.stdout or "", file=out)
    if fe_proc.returncode != 0:
        print(f"feature_extractor failed with exit code {fe_proc.returncode}", file=err)
        return 1

    print("Running: colmap exhaustive_matcher ...", file=out)
    m_help = colmap.run(["exhaustive_matcher", "-h"], timeout_s=20).stdout.lower()
    use_feature_matching_gpu = "featurematching.use_gpu" in m_help
    use_sift_matching_gpu = "siftmatching.use_gpu" in m_help
    m_cmd = ["exhaustive_matcher", "--database_path", str(db_path)]
    if use_feature_matching_gpu:
        m_cmd += ["--FeatureMatching.use_gpu", "1", "--FeatureMatching.gpu_index", "-1"]
    elif use_sift_matching_gpu:
        m_cmd += ["--SiftMatching.use_gpu", "1", "--SiftMatching.gpu_index", "-1"]
    m_proc = colmap.run(m_cmd, timeout_s=None)
    print(m_proc.stdout or "", file=out)
    if m_proc.returncode != 0:
        print(f"exhaustive_matcher failed with exit code {m_proc.returncode}", file=err)
        return 1

    # S2.2 injection: overwrite DB intrinsics from JSON (even though we already set camera_params).
    from cinetracker.core.tracking_intrinsics import inject_fixed_intrinsics_from_json

    print("Injecting fixed intrinsics into database.db ...", file=out)
    rc = inject_fixed_intrinsics_from_json(
        database_path=str(db_path),
        lens_json_path=str(lens_json),
        camera_id=None,
        update_all=False,
        dry_run=False,
    )
    if rc != 0:
        print("Intrinsics injection failed.", file=err)
        return rc

    print("Running: colmap mapper (intrinsics refinement disabled) ...", file=out)
    sparse_out.mkdir(parents=True, exist_ok=True)
    mapper_args = FixedIntrinsicsMapperArgs().to_cli_args()
    mapper_cmd = [
        "mapper",
        "--database_path",
        str(db_path),
        "--image_path",
        str(work_images),
        "--output_path",
        str(sparse_out),
        *mapper_args,
    ]
    mapper_proc = colmap.run(mapper_cmd, timeout_s=None)
    print(mapper_proc.stdout or "", file=out)
    if mapper_proc.returncode != 0:
        print(f"mapper failed with exit code {mapper_proc.returncode}", file=err)
        return 1

    # Verify output camera intrinsics match injected JSON.
    from cinetracker.core.colmap_reader import COLMAPReader

    cams = COLMAPReader(model_out).read_cameras_bin()
    if not cams:
        print("No cameras found in output model.", file=err)
        return 1
    cam = cams[min(cams.keys())]
    injected = load_intrinsics_spec(lens_json, override_model="OPENCV").params_in_colmap_order()
    got = cam.params.tolist()

    if cam.model_name.upper() != "OPENCV":
        print(f"Unexpected output camera model: {cam.model_name}", file=err)
        return 1

    if len(got) != len(injected):
        print(f"Unexpected output param length: {len(got)} != {len(injected)}", file=err)
        return 1

    max_abs = max(abs(a - b) for a, b in zip(got, injected))
    print(f"Injected params (OPENCV): {injected}", file=out)
    print(f"Output   params (OPENCV): {got}", file=out)
    print(f"Max abs diff: {max_abs:.3e}", file=out)
    if max_abs > 1e-10:
        print("FAIL: Intrinsics changed (should be frozen).", file=err)
        return 1

    print("PASS: Intrinsics remained unchanged (frozen).", file=out)

    print("Inspecting output model summary:", file=out)
    return inspect_model(model_dir=str(model_out), limit=1, out=out, err=err)

