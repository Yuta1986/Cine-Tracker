from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from cinetracker.core.colmap_cli import COLMAP
from cinetracker.core.model_inspect import inspect_model


DEFAULT_SOUTH_BUILDING_URL = "https://github.com/colmap/colmap/releases/download/3.11.1/south-building.zip"


@dataclass(frozen=True)
class SfmTestPaths:
    root: Path
    dataset_zip: Path
    dataset_dir: Path
    source_image_dir: Path
    work_image_dir: Path
    database_path: Path
    sparse_out: Path


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


def run_basic_sfm_test(
    *,
    work_dir: str | Path,
    dataset_url: str,
    force_redownload: bool,
    max_images: int,
    colmap_bin: str | None,
    out: TextIO,
    err: TextIO,
) -> int:
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)

    paths = SfmTestPaths(
        root=root,
        dataset_zip=root / "south-building.zip",
        dataset_dir=root / "south-building",
        source_image_dir=root / "south-building" / "images",
        work_image_dir=root / "images",
        database_path=root / "database.db",
        sparse_out=root / "sparse",
    )

    if force_redownload and paths.dataset_zip.exists():
        paths.dataset_zip.unlink()
    if force_redownload and paths.dataset_dir.exists():
        shutil.rmtree(paths.dataset_dir)

    try:
        _download(dataset_url, paths.dataset_zip, out)
        # We extract into root/south-building/* (as provided by the dataset).
        _extract_zip(paths.dataset_zip, root, expected_path=paths.dataset_dir / "images", out=out)
    except Exception as e:
        print(f"Dataset setup failed: {e}", file=err)
        return 1

    if not paths.source_image_dir.exists():
        print(f"Expected images dir not found: {paths.source_image_dir}", file=err)
        return 1

    colmap = COLMAP.resolve(explicit=colmap_bin)
    print(f"Using COLMAP: {colmap.path}", file=out)
    ver = colmap.version_line()
    if ver:
        print(f"COLMAP version: {ver}", file=out)

    # Build a fresh, local database to avoid cross-OS SQLite locking issues with the dataset-provided DB.
    if paths.database_path.exists():
        paths.database_path.unlink()

    if paths.work_image_dir.exists():
        shutil.rmtree(paths.work_image_dir)
    paths.work_image_dir.mkdir(parents=True, exist_ok=True)

    images = sorted([p for p in paths.source_image_dir.iterdir() if p.is_file()])
    if not images:
        print(f"No images found in: {paths.source_image_dir}", file=err)
        return 1
    if max_images > 0:
        images = images[:max_images]
    print(f"Copying {len(images)} images into workdir: {paths.work_image_dir}", file=out)
    for p in images:
        shutil.copy2(p, paths.work_image_dir / p.name)

    # Detect GPU flag naming (COLMAP 3.13+ uses FeatureExtraction/FeatureMatching).
    fe_help = colmap.run(["feature_extractor", "-h"], timeout_s=20).stdout.lower()
    use_feature_gpu = "featureextraction.use_gpu" in fe_help
    use_sift_gpu = "siftextraction.use_gpu" in fe_help

    print("Running: colmap feature_extractor ...", file=out)
    fe_cmd = [
        "feature_extractor",
        "--database_path",
        str(paths.database_path),
        "--image_path",
        str(paths.work_image_dir),
        "--ImageReader.single_camera",
        "1",
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
    m_cmd = ["exhaustive_matcher", "--database_path", str(paths.database_path)]
    if use_feature_matching_gpu:
        m_cmd += ["--FeatureMatching.use_gpu", "1", "--FeatureMatching.gpu_index", "-1"]
    elif use_sift_matching_gpu:
        m_cmd += ["--SiftMatching.use_gpu", "1", "--SiftMatching.gpu_index", "-1"]
    m_proc = colmap.run(m_cmd, timeout_s=None)
    print(m_proc.stdout or "", file=out)
    if m_proc.returncode != 0:
        print(f"exhaustive_matcher failed with exit code {m_proc.returncode}", file=err)
        return 1

    paths.sparse_out.mkdir(parents=True, exist_ok=True)
    mapper_out = paths.sparse_out / "0"
    if mapper_out.exists() and any(mapper_out.iterdir()):
        print(f"Using existing mapper output: {mapper_out}", file=out)
    else:
        print("Running: colmap mapper ...", file=out)
        proc = colmap.run(
            [
                "mapper",
                "--database_path",
                str(paths.database_path),
                "--image_path",
                str(paths.work_image_dir),
                "--output_path",
                str(paths.sparse_out),
            ],
            timeout_s=None,
        )
        print(proc.stdout or "", file=out)
        if proc.returncode != 0:
            print(f"COLMAP mapper failed with exit code {proc.returncode}", file=err)
            return 1

    if not (mapper_out / "cameras.bin").exists() or not (mapper_out / "images.bin").exists():
        print(f"Expected model outputs not found in: {mapper_out}", file=err)
        return 1

    print("Inspecting resulting model (cameras.bin/images.bin/points3D.bin):", file=out)
    return inspect_model(model_dir=str(mapper_out), limit=1, out=out, err=err)
