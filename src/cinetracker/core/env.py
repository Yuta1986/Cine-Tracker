from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BinaryProbe:
    name: str
    path: str | None
    ok: bool
    version_text: str | None
    error: str | None


def _candidate_paths(name: str) -> list[str]:
    candidates: list[str] = []
    suffixes: list[str] = [""]
    if platform.system().lower().startswith("win"):
        suffixes = [".exe", ".bat", ".cmd", ""]

    for suffix in suffixes:
        candidates.append(name + suffix)

    return candidates


def resolve_executable(name: str, env_var: str | None = None, extra: Iterable[str] = ()) -> str | None:
    if env_var:
        override = os.environ.get(env_var)
        if override:
            p = Path(override)
            if p.exists():
                return str(p)
            found = shutil.which(override)
            if found:
                return found

    for item in extra:
        if not item:
            continue
        p = Path(item)
        if p.exists():
            return str(p)

    for candidate in _candidate_paths(name):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def run_subprocess_test(argv: list[str], timeout_s: float = 10.0) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_s,
        )
        return proc.returncode == 0, (proc.stdout or "").strip()
    except Exception as e:
        return False, str(e)


def probe_binary(name: str, *, env_var: str | None = None, version_args: list[str]) -> BinaryProbe:
    path = resolve_executable(name, env_var=env_var)
    if not path:
        return BinaryProbe(
            name=name,
            path=None,
            ok=False,
            version_text=None,
            error=f"{name} not found in PATH (set {env_var} or install it)" if env_var else f"{name} not found in PATH",
        )

    ok, out = run_subprocess_test([path, *version_args])
    return BinaryProbe(name=name, path=path, ok=ok, version_text=out or None, error=None if ok else out or "non-zero exit")


def python_runtime_summary() -> dict[str, str]:
    return {
        "python": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "platform": platform.platform(),
    }
