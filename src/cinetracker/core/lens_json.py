from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cinetracker.core.colmap_binary_reader import simple_radial_to_opencv_params


@dataclass(frozen=True)
class OpenCvIntrinsics:
    """
    Canonical intrinsics for Sprint 2+:
    - OPENCV 8-parameter model in COLMAP order: fx, fy, cx, cy, k1, k2, p1, p2
    """

    image_width: int
    image_height: int
    fx: float
    fy: float
    cx: float
    cy: float
    k1: float
    k2: float
    p1: float
    p2: float

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "camera_model": "OPENCV",
            "image_width": int(self.image_width),
            "image_height": int(self.image_height),
            "fx": float(self.fx),
            "fy": float(self.fy),
            "cx": float(self.cx),
            "cy": float(self.cy),
            "k1": float(self.k1),
            "k2": float(self.k2),
            "p1": float(self.p1),
            "p2": float(self.p2),
        }


def opencv_intrinsics_from_colmap_camera(
    *,
    model_name: str,
    width: int,
    height: int,
    params: list[float],
) -> OpenCvIntrinsics:
    """
    Convert a COLMAP camera model + params into canonical OPENCV intrinsics for JSON export.

    Supported inputs:
    - OPENCV: [fx, fy, cx, cy, k1, k2, p1, p2]
    - PINHOLE: [fx, fy, cx, cy] (distortion zeroed)
    - SIMPLE_PINHOLE: [f, cx, cy] (fx=fy=f, distortion zeroed)
    - SIMPLE_RADIAL: [f, cx, cy, k] (k maps to k1, others zeroed)
    - RADIAL: [f, cx, cy, k1, k2] (fx=fy=f, p1=p2=0)

    Anything else should be converted upstream (or extended here) to meet the project constraint:
    OPENCV JSON output for UE Brown-Conrady import.
    """

    name = model_name.upper()
    if name == "OPENCV":
        if len(params) != 8:
            raise ValueError(f"OPENCV expects 8 params, got {len(params)}")
        fx, fy, cx, cy, k1, k2, p1, p2 = params
        return OpenCvIntrinsics(
            image_width=width,
            image_height=height,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            k1=k1,
            k2=k2,
            p1=p1,
            p2=p2,
        )

    if name == "PINHOLE":
        if len(params) != 4:
            raise ValueError(f"PINHOLE expects 4 params, got {len(params)}")
        fx, fy, cx, cy = params
        return OpenCvIntrinsics(width, height, fx, fy, cx, cy, 0.0, 0.0, 0.0, 0.0)

    if name == "SIMPLE_PINHOLE":
        if len(params) != 3:
            raise ValueError(f"SIMPLE_PINHOLE expects 3 params, got {len(params)}")
        f, cx, cy = params
        return OpenCvIntrinsics(width, height, f, f, cx, cy, 0.0, 0.0, 0.0, 0.0)

    if name == "SIMPLE_RADIAL":
        if len(params) != 4:
            raise ValueError(f"SIMPLE_RADIAL expects 4 params, got {len(params)}")
        f, cx, cy, k = params
        m = simple_radial_to_opencv_params(f, cx, cy, k)
        return OpenCvIntrinsics(
            image_width=width,
            image_height=height,
            fx=m["fx"],
            fy=m["fy"],
            cx=m["cx"],
            cy=m["cy"],
            k1=m["k1"],
            k2=m["k2"],
            p1=m["p1"],
            p2=m["p2"],
        )

    if name == "RADIAL":
        if len(params) != 5:
            raise ValueError(f"RADIAL expects 5 params, got {len(params)}")
        f, cx, cy, k1, k2 = params
        return OpenCvIntrinsics(width, height, f, f, cx, cy, k1, k2, 0.0, 0.0)

    raise ValueError(f"Unsupported COLMAP camera model for OPENCV JSON export: {model_name}")


def write_lens_calibration_json(data: dict[str, Any], path: str | Path) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")

