from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    here = start or Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / "pyproject.toml").is_file():
            return p
    return Path.cwd()


def repo_third_party_bin() -> Path:
    return find_repo_root() / "third_party" / "bin"

