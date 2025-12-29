from __future__ import annotations

import os
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cinetracker.core.env import resolve_executable
from cinetracker.core.paths import repo_third_party_bin


DEFAULT_GPU_ARGS = {
    "FeatureExtraction.use_gpu": "1",
    "FeatureMatching.use_gpu": "1",
    "FeatureExtraction.gpu_index": "-1",
    "FeatureMatching.gpu_index": "-1",
    "SiftExtraction.use_gpu": "1",
    "SiftMatching.use_gpu": "1",
    "SiftExtraction.gpu_index": "-1",
    "SiftMatching.gpu_index": "-1",
}


@dataclass(frozen=True)
class COLMAP:
    path: str

    @staticmethod
    def resolve(explicit: str | None = None) -> "COLMAP":
        if explicit:
            return COLMAP(explicit)
        env_path = os.environ.get("COLMAP_BIN")
        if env_path:
            return COLMAP(env_path)
        repo_candidate_exe = repo_third_party_bin() / "colmap.exe"
        if repo_candidate_exe.exists():
            return COLMAP(str(repo_candidate_exe))
        repo_candidate = repo_third_party_bin() / "colmap"
        if repo_candidate.exists():
            return COLMAP(str(repo_candidate))
        found = resolve_executable("colmap", env_var=None)
        if found:
            return COLMAP(found)
        raise FileNotFoundError("COLMAP binary not found (set COLMAP_BIN or run scripts/bootstrap_binaries_linux.sh)")

    def run(
        self,
        args: list[str],
        *,
        extra_env: Mapping[str, str] | None = None,
        cwd: str | Path | None = None,
        timeout_s: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if extra_env:
            env.update({k: str(v) for k, v in extra_env.items()})
        cmd = [self.path, *self._maybe_convert_args(args)]
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            timeout=timeout_s,
        )

    def _maybe_convert_args(self, args: list[str]) -> list[str]:
        if not self.path.lower().endswith(".exe"):
            return args
        if not shutil.which("wslpath"):
            return args

        converted: list[str] = []
        for a in args:
            if _looks_like_path(a):
                converted.append(_wsl_to_win_path(a))
            else:
                converted.append(a)
        return converted

    def version_line(self) -> str | None:
        proc = self.run(["-h"], timeout_s=10)
        if proc.stdout:
            return proc.stdout.splitlines()[0].strip()
        return None


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith("--"):
        return False
    if value.isdigit():
        return False
    if "/" not in value and "\\" not in value:
        return False
    p = Path(value)
    if p.exists():
        return True
    if p.parent.exists():
        return True
    return False


def _wsl_to_win_path(value: str) -> str:
    proc = subprocess.run(
        ["wslpath", "-w", value],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    out = (proc.stdout or "").strip()
    return out or value
