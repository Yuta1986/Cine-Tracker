"""
S4.1 — Lens File Asset Creation

Reads `lens_calibration_data.json` (OPENCV keys) and creates/populates a Lens File asset.

Expected input dict keys (from Cine-Tracker):
  image_width, image_height, fx, fy, cx, cy, k1, k2, p1, p2

Run inside UE Python:
  - Enable the Camera Calibration / Lens Distortion plugins.
  - Use the UE Output Log to see printed diagnostics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import unreal


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _px_to_mm(fx_px: float, image_width_px: int, sensor_width_mm: float) -> float:
    return float(fx_px) * float(sensor_width_mm) / float(image_width_px)


def _principal_point_uv(cx_px: float, cy_px: float, w: int, h: int) -> tuple[float, float]:
    return (float(cx_px) / float(w), float(cy_px) / float(h))


def _create_lens_file(asset_path: str, asset_name: str) -> unreal.Object:
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    asset = tools.create_asset(
        asset_name,
        asset_path,
        unreal.LensFile,
        unreal.LensFileFactoryNew(),
    )
    if not asset:
        raise RuntimeError("Failed to create LensFile asset")
    return asset


def _try_set_brown_conrady(asset: unreal.Object, lens_data: dict[str, Any]) -> None:
    """
    Best-effort population:
    - Set distortion model to Brown-Conrady when available.
    - Add a distortion data point if public APIs exist.
    """

    k1 = float(lens_data.get("k1", 0.0))
    k2 = float(lens_data.get("k2", 0.0))
    p1 = float(lens_data.get("p1", 0.0))
    p2 = float(lens_data.get("p2", 0.0))

    # Some UE versions expose explicit BrownConrady structs.
    distortion_struct = None
    if hasattr(unreal, "BrownConradyModel"):
        distortion_struct = unreal.BrownConradyModel()
        for prop, val in [("k1", k1), ("k2", k2), ("p1", p1), ("p2", p2)]:
            if distortion_struct.has_editor_property(prop):
                distortion_struct.set_editor_property(prop, val)

    # Public APIs vary; attempt to find an "add distortion point" style method.
    candidate_methods = [
        "add_distortion_point",
        "add_distortion_data_point",
        "add_lens_distortion_point",
    ]
    for m in candidate_methods:
        if hasattr(asset, m):
            fn = getattr(asset, m)
            try:
                # Common signature is (focus, zoom, distortion_struct)
                fn(0.0, 0.0, distortion_struct)  # type: ignore[misc]
                unreal.log(f"LensFile: populated distortion via {m}()")
                return
            except Exception as e:
                unreal.log_warning(f"LensFile: {m}() exists but failed: {e}")

    unreal.log_warning(
        "LensFile: could not find a public distortion-point API; "
        "asset was created but may require manual population depending on UE version."
    )


def create_lens_file_from_json(
    lens_data: dict[str, Any],
    *,
    asset_path: str,
    asset_name: str,
    sensor_width_mm: float = 36.0,
) -> unreal.Object:
    """
    Create a LensFile asset and attempt to populate:
    - Distortion parameters (Brown-Conrady)
    - Focal length / image center metadata (where API exists)
    """

    required = ["image_width", "image_height", "fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2"]
    missing = [k for k in required if k not in lens_data]
    if missing:
        raise ValueError(f"lens_data missing required keys: {missing}")

    w = int(lens_data["image_width"])
    h = int(lens_data["image_height"])
    fx = float(lens_data["fx"])
    cx = float(lens_data["cx"])
    cy = float(lens_data["cy"])

    focal_mm = _px_to_mm(fx, w, sensor_width_mm)
    pp_u, pp_v = _principal_point_uv(cx, cy, w, h)

    asset = _create_lens_file(asset_path, asset_name)
    unreal.log(f"Created LensFile: {asset.get_path_name()}")
    unreal.log(f"Derived focal_length_mm={focal_mm:.6g} (sensor_width_mm={sensor_width_mm})")
    unreal.log(f"Derived principal_point_uv=({pp_u:.6g}, {pp_v:.6g})")

    _try_set_brown_conrady(asset, lens_data)

    # Save asset
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return asset


def main(
    lens_json_path: str,
    asset_path: str = "/Game/VP/CalibratedLens",
    asset_name: str = "LensFile_CineTracker",
) -> None:
    lens_data = _load_json(lens_json_path)
    create_lens_file_from_json(lens_data, asset_path=asset_path, asset_name=asset_name)


# Example (run from UE python console):
# main(r"C:\path\to\lens_calibration_data.json")

