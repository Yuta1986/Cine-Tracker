from __future__ import annotations

from pathlib import Path
from typing import TextIO

from cinetracker.core.colmap_db import COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES
from cinetracker.core.colmap_reader import COLMAPReader
import struct


def _read_u64(path: Path) -> int:
    with path.open("rb") as f:
        raw = f.read(8)
    if len(raw) != 8:
        raise ValueError(f"File too small to contain header count: {path}")
    return struct.unpack("<Q", raw)[0]


def inspect_model(*, model_dir: str | Path, limit: int, out: TextIO, err: TextIO) -> int:
    model_path = Path(model_dir)
    if not model_path.exists():
        print(f"Model dir not found: {model_path}", file=err)
        return 2

    reader = COLMAPReader(model_path)
    cameras_bin = reader.cameras_path()
    images_bin = reader.images_path()
    points_bin = reader.points3d_path()

    missing = [p for p in [cameras_bin, images_bin, points_bin] if not p.exists()]
    if missing:
        print("Missing expected COLMAP model files:", file=err)
        for p in missing:
            print(f"  {p}", file=err)
        return 2

    try:
        cam_header = _read_u64(cameras_bin)
        img_header = _read_u64(images_bin)
        pts_header = _read_u64(points_bin)
        cameras, images, points = reader.load()
    except Exception as e:
        print(f"Failed to read model: {e}", file=err)
        return 1

    print(f"Model dir: {model_path}", file=out)
    print(f"Header counts: cameras.bin={cam_header} images.bin={img_header} points3D.bin={pts_header}", file=out)
    print(f"Counts: cameras={len(cameras)} images={len(images)} points3D={len(points)}", file=out)

    cam_items = list(cameras.values())[: max(0, limit)]
    for cam in cam_items:
        names = COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES.get(cam.model_id, [])
        params = ", ".join(f"{n}={v:.6g}" for n, v in zip(names, cam.params.tolist()))
        print(
            f"Camera {cam.camera_id}: model={cam.model_name}({cam.model_id}) size={cam.width}x{cam.height} {params}",
            file=out,
        )

    img_items = list(images.values())[: max(0, limit)]
    for img in img_items:
        q = ", ".join(f"{v:.6g}" for v in img.qvec.tolist())
        t = ", ".join(f"{v:.6g}" for v in img.tvec.tolist())
        print(
            f"Image {img.image_id}: camera_id={img.camera_id} name={img.name} qvec=[{q}] tvec=[{t}] points2D={len(img.point3D_ids)}",
            file=out,
        )

    centers = reader.camera_centers_world(images)
    if len(centers) > 0:
        c0 = ", ".join(f"{v:.6g}" for v in centers[0].tolist())
        print(f"Camera center (first image, world): [{c0}]", file=out)

    xyz = reader.points_xyz(points)
    if len(xyz) > 0:
        p0 = ", ".join(f"{v:.6g}" for v in xyz[0].tolist())
        print(f"Point3D xyz (first): [{p0}]", file=out)

    return 0
