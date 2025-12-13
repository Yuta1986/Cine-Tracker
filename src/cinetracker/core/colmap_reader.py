from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover
    np = None  # type: ignore[assignment]

from cinetracker.core.colmap_db import (
    COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES,
    COLMAP_CAMERA_MODEL_NAME_TO_ID,
)


def _read_next_bytes(fid: BinaryIO, num_bytes: int, fmt: str):
    data = fid.read(num_bytes)
    if len(data) != num_bytes:
        raise EOFError(f"Unexpected EOF: wanted {num_bytes} bytes, got {len(data)}")
    return struct.unpack("<" + fmt, data)


def _read_c_string(fid: BinaryIO) -> str:
    chars = bytearray()
    while True:
        ch = fid.read(1)
        if ch == b"":
            raise EOFError("Unexpected EOF reading C-string")
        if ch == b"\x00":
            break
        chars.extend(ch)
    return chars.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class Camera:
    camera_id: int
    model_id: int
    model_name: str
    width: int
    height: int
    params: "np.ndarray"  # (P,)


@dataclass(frozen=True)
class Image:
    image_id: int
    qvec: "np.ndarray"  # (4,) qw,qx,qy,qz
    tvec: "np.ndarray"  # (3,)
    camera_id: int
    name: str
    xys: "np.ndarray"  # (N,2)
    point3D_ids: "np.ndarray"  # (N,)


@dataclass(frozen=True)
class Point3D:
    point3D_id: int
    xyz: "np.ndarray"  # (3,)
    rgb: "np.ndarray"  # (3,) uint8
    error: float
    track_image_ids: "np.ndarray"  # (T,)
    track_point2D_idxs: "np.ndarray"  # (T,)


def _require_numpy():
    if np is None:
        raise RuntimeError("numpy is required for COLMAP binary reading; install with `pip install -e .[core]`")


def qvec_to_rotmat(qvec: "np.ndarray") -> "np.ndarray":
    _require_numpy()
    q = np.asarray(qvec, dtype=np.float64).reshape(4)  # type: ignore[union-attr]
    qw, qx, qy, qz = q
    return np.array(  # type: ignore[union-attr]
        [
            [1 - 2 * (qy**2 + qz**2), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
            [2 * (qx * qy + qw * qz), 1 - 2 * (qx**2 + qz**2), 2 * (qy * qz - qw * qx)],
            [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx**2 + qy**2)],
        ],
        dtype=np.float64,  # type: ignore[union-attr]
    )


def colmap_world_to_camera_to_c2w(qvec: "np.ndarray", tvec: "np.ndarray") -> "np.ndarray":
    _require_numpy()
    r_w2c = qvec_to_rotmat(qvec)
    r_c2w = r_w2c.T
    c = -r_c2w @ np.asarray(tvec, dtype=np.float64).reshape(3)  # type: ignore[union-attr]
    t = np.eye(4, dtype=np.float64)  # type: ignore[union-attr]
    t[:3, :3] = r_c2w
    t[:3, 3] = c
    return t


class COLMAPReader:
    def __init__(self, model_dir: str | Path):
        _require_numpy()
        self.model_dir = Path(model_dir)

    def cameras_path(self) -> Path:
        return self.model_dir / "cameras.bin"

    def images_path(self) -> Path:
        return self.model_dir / "images.bin"

    def points3d_path(self) -> Path:
        return self.model_dir / "points3D.bin"

    def read_cameras_bin(self) -> dict[int, Camera]:
        _require_numpy()
        path = self.cameras_path()
        cameras: dict[int, Camera] = {}
        with path.open("rb") as fid:
            num_cameras = _read_next_bytes(fid, 8, "Q")[0]
            for _ in range(num_cameras):
                camera_id = int(_read_next_bytes(fid, 4, "i")[0])
                model_id = int(_read_next_bytes(fid, 4, "i")[0])
                width = int(_read_next_bytes(fid, 8, "Q")[0])
                height = int(_read_next_bytes(fid, 8, "Q")[0])

                param_names = COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES.get(model_id)
                if not param_names:
                    raise ValueError(f"Unsupported/unknown camera model id in cameras.bin: {model_id}")
                num_params = len(param_names)
                params = np.array(  # type: ignore[union-attr]
                    _read_next_bytes(fid, 8 * num_params, "d" * num_params),
                    dtype=np.float64,  # type: ignore[union-attr]
                )
                model_name = next(
                    (k for k, v in COLMAP_CAMERA_MODEL_NAME_TO_ID.items() if v == model_id),
                    f"UNKNOWN({model_id})",
                )
                cameras[camera_id] = Camera(
                    camera_id=camera_id,
                    model_id=model_id,
                    model_name=model_name,
                    width=width,
                    height=height,
                    params=params,
                )
        return cameras

    def read_images_bin(self) -> dict[int, Image]:
        _require_numpy()
        path = self.images_path()
        images: dict[int, Image] = {}
        with path.open("rb") as fid:
            num_images = _read_next_bytes(fid, 8, "Q")[0]
            for _ in range(num_images):
                image_id = int(_read_next_bytes(fid, 4, "i")[0])
                qvec = np.array(_read_next_bytes(fid, 8 * 4, "dddd"), dtype=np.float64)  # type: ignore[union-attr]
                tvec = np.array(_read_next_bytes(fid, 8 * 3, "ddd"), dtype=np.float64)  # type: ignore[union-attr]
                camera_id = int(_read_next_bytes(fid, 4, "i")[0])
                name = _read_c_string(fid)
                num_points2d = int(_read_next_bytes(fid, 8, "Q")[0])

                xys = np.empty((num_points2d, 2), dtype=np.float64)  # type: ignore[union-attr]
                point3d_ids = np.empty((num_points2d,), dtype=np.int64)  # type: ignore[union-attr]
                for i in range(num_points2d):
                    x, y = _read_next_bytes(fid, 16, "dd")
                    point3d_id = _read_next_bytes(fid, 8, "q")[0]
                    xys[i, 0] = x
                    xys[i, 1] = y
                    point3d_ids[i] = point3d_id

                images[image_id] = Image(
                    image_id=image_id,
                    qvec=qvec,
                    tvec=tvec,
                    camera_id=camera_id,
                    name=name,
                    xys=xys,
                    point3D_ids=point3d_ids,
                )
        return images

    def read_points3d_bin(self) -> dict[int, Point3D]:
        _require_numpy()
        path = self.points3d_path()
        points: dict[int, Point3D] = {}
        with path.open("rb") as fid:
            num_points = _read_next_bytes(fid, 8, "Q")[0]
            for _ in range(num_points):
                point3d_id = int(_read_next_bytes(fid, 8, "Q")[0])
                xyz = np.array(_read_next_bytes(fid, 24, "ddd"), dtype=np.float64)  # type: ignore[union-attr]
                rgb = np.array(_read_next_bytes(fid, 3, "BBB"), dtype=np.uint8)  # type: ignore[union-attr]
                error = float(_read_next_bytes(fid, 8, "d")[0])
                track_len = int(_read_next_bytes(fid, 8, "Q")[0])
                image_ids = np.empty((track_len,), dtype=np.int32)  # type: ignore[union-attr]
                point2d_idxs = np.empty((track_len,), dtype=np.int32)  # type: ignore[union-attr]
                for i in range(track_len):
                    image_id = int(_read_next_bytes(fid, 4, "i")[0])
                    point2d_idx = int(_read_next_bytes(fid, 4, "i")[0])
                    image_ids[i] = image_id
                    point2d_idxs[i] = point2d_idx
                points[point3d_id] = Point3D(
                    point3D_id=point3d_id,
                    xyz=xyz,
                    rgb=rgb,
                    error=error,
                    track_image_ids=image_ids,
                    track_point2D_idxs=point2d_idxs,
                )
        return points

    def load(self) -> tuple[dict[int, Camera], dict[int, Image], dict[int, Point3D]]:
        return self.read_cameras_bin(), self.read_images_bin(), self.read_points3d_bin()

    def camera_centers_world(self, images: dict[int, Image]) -> np.ndarray:
        _require_numpy()
        centers = []
        for img in images.values():
            t_c2w = colmap_world_to_camera_to_c2w(img.qvec, img.tvec)
            centers.append(t_c2w[:3, 3])
        if not centers:
            return np.empty((0, 3), dtype=np.float64)  # type: ignore[union-attr]
        return np.stack(centers, axis=0)  # type: ignore[union-attr]

    def points_xyz(self, points: dict[int, Point3D]) -> np.ndarray:
        _require_numpy()
        xyz = [p.xyz for p in points.values()]
        if not xyz:
            return np.empty((0, 3), dtype=np.float64)  # type: ignore[union-attr]
        return np.stack(xyz, axis=0)  # type: ignore[union-attr]
