from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def profiles_dir() -> Path:
    override = os.environ.get("CINETRACKER_PROFILE_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cinetracker" / "profiles"


def sanitize_profile_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        raise ValueError("Profile name is empty")
    raw = raw.replace(" ", "_")
    safe = _SAFE_NAME_RE.sub("_", raw).strip("._-")
    if not safe:
        raise ValueError("Profile name becomes empty after sanitization")
    return safe


def profile_json_path(name: str) -> Path:
    safe = sanitize_profile_name(name)
    return profiles_dir() / f"{safe}.json"


def profile_meta_path(name: str) -> Path:
    safe = sanitize_profile_name(name)
    return profiles_dir() / f"{safe}.meta.json"


@dataclass(frozen=True)
class LensProfile:
    name: str
    json_path: Path
    meta_path: Path | None
    camera_model: str | None
    image_width: int | None
    image_height: int | None
    created_at: str | None
    display_name: str | None


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def _summarize_lens_json(data: Any) -> tuple[str | None, int | None, int | None]:
    if not isinstance(data, dict):
        return None, None, None
    camera_model = data.get("camera_model") or data.get("model")
    if not isinstance(camera_model, str):
        camera_model = None
    width = data.get("image_width") or data.get("width")
    height = data.get("image_height") or data.get("height")
    if not isinstance(width, int):
        width = None
    if not isinstance(height, int):
        height = None
    return camera_model, width, height


def add_profile(*, name: str, json_path: str | Path, overwrite: bool = False) -> Path:
    src = Path(json_path)
    if not src.exists():
        raise FileNotFoundError(str(src))

    data = _read_json(src)
    camera_model, width, height = _summarize_lens_json(data)

    safe = sanitize_profile_name(name)
    dst_json = profiles_dir() / f"{safe}.json"
    dst_meta = profiles_dir() / f"{safe}.meta.json"

    if dst_json.exists() and not overwrite:
        raise FileExistsError(f"Profile already exists: {safe}")

    dst_json.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_json)

    meta = {
        "version": 1,
        "display_name": name,
        "safe_name": safe,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_json": str(src),
        "camera_model": camera_model,
        "image_width": width,
        "image_height": height,
    }
    _write_json(dst_meta, meta)
    return dst_json


def remove_profile(*, name: str) -> None:
    p_json = profile_json_path(name)
    p_meta = profile_meta_path(name)
    if p_json.exists():
        p_json.unlink()
    if p_meta.exists():
        p_meta.unlink()


def resolve_profile_json(name: str) -> Path:
    p = profile_json_path(name)
    if not p.exists():
        safe = sanitize_profile_name(name)
        raise FileNotFoundError(f"Lens profile not found: {safe} (expected {p})")
    return p


def load_profile(name: str) -> LensProfile:
    safe = sanitize_profile_name(name)
    p_json = profiles_dir() / f"{safe}.json"
    p_meta = profiles_dir() / f"{safe}.meta.json"
    meta = None
    if p_meta.exists():
        try:
            meta = _read_json(p_meta)
        except Exception:
            meta = None

    camera_model = None
    width = None
    height = None
    if p_json.exists():
        try:
            data = _read_json(p_json)
            camera_model, width, height = _summarize_lens_json(data)
        except Exception:
            pass

    created_at = meta.get("created_at") if isinstance(meta, dict) else None
    display_name = meta.get("display_name") if isinstance(meta, dict) else None
    return LensProfile(
        name=safe,
        json_path=p_json,
        meta_path=p_meta if p_meta.exists() else None,
        camera_model=camera_model,
        image_width=width,
        image_height=height,
        created_at=created_at if isinstance(created_at, str) else None,
        display_name=display_name if isinstance(display_name, str) else None,
    )


def list_profiles() -> list[LensProfile]:
    d = profiles_dir()
    if not d.exists():
        return []
    profiles: list[LensProfile] = []
    for p in sorted(d.glob("*.json")):
        if p.name.endswith(".meta.json"):
            continue
        safe = p.stem
        profiles.append(load_profile(safe))
    return profiles

