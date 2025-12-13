from __future__ import annotations

import json
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TextIO


COLMAP_CAMERA_MODEL_NAME_TO_ID: dict[str, int] = {
    "SIMPLE_PINHOLE": 0,
    "PINHOLE": 1,
    "SIMPLE_RADIAL": 2,
    "RADIAL": 3,
    "OPENCV": 4,
    "OPENCV_FISHEYE": 5,
    "FULL_OPENCV": 6,
    "FOV": 7,
    "SIMPLE_RADIAL_FISHEYE": 8,
    "RADIAL_FISHEYE": 9,
    "THIN_PRISM_FISHEYE": 10,
}

COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES: dict[int, list[str]] = {
    0: ["f", "cx", "cy"],
    1: ["fx", "fy", "cx", "cy"],
    2: ["f", "cx", "cy", "k"],
    3: ["f", "cx", "cy", "k1", "k2"],
    4: ["fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2"],
    5: ["fx", "fy", "cx", "cy", "k1", "k2", "k3", "k4"],
    6: ["fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6"],
    7: ["fx", "fy", "cx", "cy", "omega"],
    8: ["f", "cx", "cy", "k"],
    9: ["f", "cx", "cy", "k1", "k2"],
    10: ["fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2", "k3", "k4", "sx1", "sy1"],
}


@dataclass(frozen=True)
class IntrinsicsSpec:
    camera_model_name: str
    image_width: int | None
    image_height: int | None
    params_by_name: dict[str, float]

    @property
    def camera_model_id(self) -> int:
        model = self.camera_model_name.upper()
        if model not in COLMAP_CAMERA_MODEL_NAME_TO_ID:
            raise ValueError(f"Unsupported COLMAP camera model: {self.camera_model_name!r}")
        return COLMAP_CAMERA_MODEL_NAME_TO_ID[model]

    def params_in_colmap_order(self) -> list[float]:
        model_id = self.camera_model_id
        param_names = COLMAP_CAMERA_MODEL_ID_TO_PARAM_NAMES.get(model_id)
        if not param_names:
            raise ValueError(f"Missing parameter definition for model id: {model_id}")

        missing = [name for name in param_names if name not in self.params_by_name]
        if missing:
            raise ValueError(f"Missing parameters for {self.camera_model_name}: {', '.join(missing)}")
        return [float(self.params_by_name[name]) for name in param_names]


def decode_params_blob(params_blob: bytes) -> list[float]:
    if len(params_blob) % 8 != 0:
        raise ValueError(f"Invalid params blob length (expected multiple of 8): {len(params_blob)}")
    count = len(params_blob) // 8
    if count == 0:
        return []
    return list(struct.unpack("<" + "d" * count, params_blob))


def encode_params_blob(params: Iterable[float]) -> bytes:
    params_list = list(params)
    return struct.pack("<" + "d" * len(params_list), *params_list)


def load_intrinsics_spec(json_path: str | Path, override_model: str | None = None) -> IntrinsicsSpec:
    path = Path(json_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("lens_calibration_data.json must be a JSON object")

    camera_model = override_model or data.get("camera_model") or data.get("model") or "OPENCV"
    if not isinstance(camera_model, str):
        raise ValueError("camera_model must be a string when present")

    width = data.get("image_width") or data.get("width")
    height = data.get("image_height") or data.get("height")
    if width is not None and not isinstance(width, int):
        raise ValueError("image_width/width must be an integer when present")
    if height is not None and not isinstance(height, int):
        raise ValueError("image_height/height must be an integer when present")

    params_by_name: dict[str, float] = {}
    for key, value in data.items():
        if key in {"version", "camera_model", "model", "image_width", "image_height", "width", "height"}:
            continue
        if isinstance(value, (int, float)):
            params_by_name[key] = float(value)

    return IntrinsicsSpec(
        camera_model_name=camera_model,
        image_width=width,
        image_height=height,
        params_by_name=params_by_name,
    )


def _ensure_cameras_table(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='cameras'"
    ).fetchone()
    if not row:
        raise RuntimeError("database has no 'cameras' table; is this a COLMAP database.db?")


def _format_camera_row(row: sqlite3.Row) -> str:
    model = row["model"]
    if isinstance(model, int):
        model_id = model
        model_name = next(
            (name for name, mid in COLMAP_CAMERA_MODEL_NAME_TO_ID.items() if mid == model_id),
            f"UNKNOWN({model_id})",
        )
    else:
        model_name = str(model)

    params_blob = row["params"]
    if isinstance(params_blob, memoryview):
        params_blob = params_blob.tobytes()
    params_preview = "?"
    try:
        decoded = decode_params_blob(params_blob)
        params_preview = ", ".join(f"{v:.6g}" for v in decoded)
    except Exception:
        pass

    return (
        f"camera_id={row['camera_id']} model={model_name} width={row['width']} height={row['height']} "
        f"prior_focal_length={row['prior_focal_length']} params=[{params_preview}]"
    )


def inject_intrinsics_into_database(
    *,
    database_path: str | Path,
    json_path: str | Path,
    camera_id: int | None = None,
    update_all: bool = False,
    override_model: str | None = None,
    set_dimensions: bool = False,
    set_prior_focal_length: bool = True,
    dry_run: bool = False,
    out: TextIO,
    err: TextIO,
) -> int:
    db_path = Path(database_path)
    js_path = Path(json_path)

    if not db_path.exists():
        print(f"Database not found: {db_path}", file=err)
        return 2
    if not js_path.exists():
        print(f"JSON not found: {js_path}", file=err)
        return 2

    try:
        intrinsics = load_intrinsics_spec(js_path, override_model=override_model)
        ordered_params = intrinsics.params_in_colmap_order()
    except Exception as e:
        print(f"Failed to load intrinsics: {e}", file=err)
        return 2

    dimensions: tuple[int, int] | None = None
    if set_dimensions:
        if intrinsics.image_width is None or intrinsics.image_height is None:
            print("--set-dimensions requires image_width/image_height in JSON", file=err)
            return 2
        dimensions = (intrinsics.image_width, intrinsics.image_height)

    model_id = intrinsics.camera_model_id
    params_blob = encode_params_blob(ordered_params)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        _ensure_cameras_table(conn)

        cameras = conn.execute(
            "SELECT camera_id, model, width, height, params, prior_focal_length FROM cameras ORDER BY camera_id"
        ).fetchall()
        if not cameras:
            print("No cameras found in database.", file=err)
            return 2

        if update_all:
            target_ids = [int(r["camera_id"]) for r in cameras]
        elif camera_id is not None:
            target_ids = [camera_id]
        elif len(cameras) == 1:
            target_ids = [int(cameras[0]["camera_id"])]
        else:
            print(
                f"Database has {len(cameras)} cameras; specify --camera-id or --all.",
                file=err,
            )
            for r in cameras:
                print("  " + _format_camera_row(r), file=err)
            return 2

        existing_by_id = {int(r["camera_id"]): r for r in cameras}
        missing = [cid for cid in target_ids if cid not in existing_by_id]
        if missing:
            print(f"Camera IDs not found in database: {missing}", file=err)
            return 2

        print("Planned updates:", file=out)
        for cid in target_ids:
            before = existing_by_id[cid]
            print("  BEFORE " + _format_camera_row(before), file=out)

            after_width = before["width"]
            after_height = before["height"]
            if dimensions is not None:
                after_width, after_height = dimensions

            after_params = ", ".join(f"{v:.6g}" for v in ordered_params)
            print(
                "  AFTER  "
                f"camera_id={cid} model={intrinsics.camera_model_name.upper()} width={after_width} height={after_height} "
                f"prior_focal_length={1 if set_prior_focal_length else 0} params=[{after_params}]",
                file=out,
            )

        if dry_run:
            print("Dry run: no changes written.", file=out)
            return 0

        conn.execute("BEGIN")
        for cid in target_ids:
            before = existing_by_id[cid]
            model_value: int | str = model_id if isinstance(before["model"], int) else intrinsics.camera_model_name.upper()

            if dimensions is not None:
                width, height = dimensions
                conn.execute(
                    "UPDATE cameras SET model=?, width=?, height=?, params=?, prior_focal_length=? WHERE camera_id=?",
                    (
                        model_value,
                        width,
                        height,
                        params_blob,
                        1 if set_prior_focal_length else 0,
                        cid,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE cameras SET model=?, params=?, prior_focal_length=? WHERE camera_id=?",
                    (model_value, params_blob, 1 if set_prior_focal_length else 0, cid),
                )

        conn.commit()
        print(f"Updated {len(target_ids)} camera(s) in {db_path}.", file=out)
        return 0
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"Error updating database: {e}", file=err)
        return 1
    finally:
        conn.close()

