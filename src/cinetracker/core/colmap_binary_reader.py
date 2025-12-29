from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from cinetracker.core.colmap_reader import COLMAPReader, Image, Point3D


@dataclass(frozen=True)
class PoseArrays:
    image_ids: np.ndarray  # (N,) int32
    names: list[str]  # (N,)
    qvecs: np.ndarray  # (N,4) float64, order: qw,qx,qy,qz (COLMAP convention)
    tvecs: np.ndarray  # (N,3) float64 (world->camera translation)


@dataclass(frozen=True)
class PointCloudArrays:
    point3D_ids: np.ndarray  # (M,) uint64
    xyz: np.ndarray  # (M,3) float64
    rgb: np.ndarray  # (M,3) uint8
    error: np.ndarray  # (M,) float64


class COLMAPBinaryReader:
    """
    Thin wrapper around `COLMAPReader` that provides "Sprint 1 friendly" NumPy-array outputs.
    """

    def __init__(self, model_dir: str | Path):
        self._reader = COLMAPReader(model_dir)

    def read_pose_arrays(
        self,
        *,
        order_by: Literal["image_id", "name"] = "image_id",
    ) -> PoseArrays:
        images = self._reader.read_images_bin()
        items: list[Image] = list(images.values())
        if order_by == "name":
            items.sort(key=lambda x: x.name)
        else:
            items.sort(key=lambda x: x.image_id)

        image_ids = np.array([im.image_id for im in items], dtype=np.int32)
        names = [im.name for im in items]
        qvecs = np.stack([im.qvec for im in items], axis=0).astype(np.float64, copy=False)
        tvecs = np.stack([im.tvec for im in items], axis=0).astype(np.float64, copy=False)
        return PoseArrays(image_ids=image_ids, names=names, qvecs=qvecs, tvecs=tvecs)

    def read_pointcloud_arrays(self) -> PointCloudArrays:
        points = self._reader.read_points3d_bin()
        items: list[Point3D] = list(points.values())
        items.sort(key=lambda p: p.point3D_id)

        point_ids = np.array([p.point3D_id for p in items], dtype=np.uint64)
        xyz = np.stack([p.xyz for p in items], axis=0).astype(np.float64, copy=False)
        rgb = np.stack([p.rgb for p in items], axis=0).astype(np.uint8, copy=False)
        error = np.array([p.error for p in items], dtype=np.float64)
        return PointCloudArrays(point3D_ids=point_ids, xyz=xyz, rgb=rgb, error=error)


def simple_radial_to_opencv_params(f: float, cx: float, cy: float, k: float) -> dict[str, float]:
    """
    Convert COLMAP SIMPLE_RADIAL (f, cx, cy, k) into OPENCV-style params.

    Policy:
    - fx = fy = f
    - k1 = k
    - k2 = 0
    - p1 = p2 = 0
    """

    return {
        "fx": float(f),
        "fy": float(f),
        "cx": float(cx),
        "cy": float(cy),
        "k1": float(k),
        "k2": 0.0,
        "p1": 0.0,
        "p2": 0.0,
    }

