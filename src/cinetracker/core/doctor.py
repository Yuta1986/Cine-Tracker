from __future__ import annotations

import subprocess
import sys
from importlib import metadata
from typing import TextIO

import os

from cinetracker.core.env import BinaryProbe, probe_binary, python_runtime_summary, run_subprocess_test
from cinetracker.core.paths import repo_third_party_bin


def _safe_pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _pip_freeze(full: bool) -> str:
    cmd = [sys.executable, "-m", "pip", "freeze"]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        txt = (proc.stdout or "").strip()
        if full:
            return txt
        lines = txt.splitlines()
        return "\n".join(lines[:50] + (["... (truncated)"] if len(lines) > 50 else []))
    except Exception as e:
        return f"pip freeze failed: {e}"


def _probe_explicit_path(name: str, path: str, version_args: list[str]) -> BinaryProbe:
    ok, text = run_subprocess_test([path, *version_args], timeout_s=10.0)
    return BinaryProbe(
        name=name,
        path=path,
        ok=ok,
        version_text=text or None,
        error=None if ok else (text or "non-zero exit"),
    )


def _probe_with_repo_fallback(name: str, env_var: str, version_args: list[str]) -> BinaryProbe:
    probe = probe_binary(name, env_var=env_var, version_args=version_args)
    if probe.path:
        return probe
    candidate_exe = repo_third_party_bin() / f"{name}.exe"
    if candidate_exe.exists():
        return _probe_explicit_path(name, str(candidate_exe), version_args)
    candidate = repo_third_party_bin() / name
    if candidate.exists():
        return _probe_explicit_path(name, str(candidate), version_args)
    return probe


def _looks_like_colmap_has_gpu_flags(colmap_path: str) -> tuple[bool, str]:
    ok, text = run_subprocess_test([colmap_path, "feature_extractor", "-h"], timeout_s=10.0)
    if not ok:
        return False, "failed to run `colmap feature_extractor -h`"
    lowered = text.lower()
    if "featureextraction.use_gpu" in lowered:
        return True, "found `FeatureExtraction.use_gpu`"
    if "siftextraction.use_gpu" in lowered:
        return True, "found `SiftExtraction.use_gpu`"
    return False, "no known GPU flag found (expected FeatureExtraction.use_gpu or SiftExtraction.use_gpu)"


def _probe_nvidia_smi() -> tuple[bool, str]:
    ok, text = run_subprocess_test(["nvidia-smi", "-L"], timeout_s=5.0)
    if not ok:
        return False, "nvidia-smi not available (or no driver/GPU visible)"
    first = text.splitlines()[0] if text else "nvidia-smi ok"
    return True, first


def run_doctor(
    *,
    full_freeze: bool,
    colmap_bin: str | None,
    ffmpeg_bin: str | None,
    check_gpu: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    runtime = python_runtime_summary()
    print("Runtime:", file=out)
    print(f"  python: {runtime['python']}", file=out)
    print(f"  executable: {runtime['executable']}", file=out)
    print(f"  platform: {runtime['platform']}", file=out)
    print(f"  venv: {'YES' if os.environ.get('VIRTUAL_ENV') else 'UNKNOWN'}", file=out)

    ffmpeg = _probe_with_repo_fallback("ffmpeg", "FFMPEG_BIN", ["-version"])
    colmap = _probe_with_repo_fallback("colmap", "COLMAP_BIN", ["-h"])
    if ffmpeg_bin:
        ffmpeg = _probe_explicit_path("ffmpeg", ffmpeg_bin, ["-version"])
    if colmap_bin:
        colmap = _probe_explicit_path("colmap", colmap_bin, ["-h"])

    print("Binaries:", file=out)
    for probe in (ffmpeg, colmap):
        if probe.path:
            status = "OK" if probe.ok else "ERROR"
            print(f"  {probe.name}: {probe.path} ({status})", file=out)
            if probe.version_text:
                first = probe.version_text.splitlines()[0]
                print(f"    output: {first}", file=out)
            print(f"    subprocess.run test: `[\"{probe.path}\", ...]`", file=out)
        else:
            print(f"  {probe.name}: MISSING", file=out)
            if probe.error:
                print(f"    hint: {probe.error}", file=out)

    if check_gpu:
        print("GPU checks:", file=out)
        if colmap.path:
            has_flag, msg = _looks_like_colmap_has_gpu_flags(colmap.path)
            print(f"  colmap GPU flags: {'YES' if has_flag else 'NO'} ({msg})", file=out)
            if colmap.version_text and "without CUDA" in colmap.version_text:
                print("  colmap CUDA build: NO (binary reports 'without CUDA')", file=out)
            elif colmap.version_text and "with CUDA" in colmap.version_text:
                print("  colmap CUDA build: YES (binary reports 'with CUDA')", file=out)
        else:
            print("  colmap GPU flags: SKIPPED (colmap missing)", file=out)

        ok, msg = _probe_nvidia_smi()
        print(f"  nvidia-smi: {'OK' if ok else 'MISSING'} ({msg})", file=out)
        print("  Recommended default args:", file=out)
        print("    --FeatureExtraction.use_gpu 1 --FeatureMatching.use_gpu 1", file=out)
        print("    (legacy) --SiftExtraction.use_gpu 1 --SiftMatching.use_gpu 1", file=out)

    print("Key Python deps:", file=out)
    for pkg in ["numpy", "PySide6"]:
        v = _safe_pkg_version(pkg)
        print(f"  {pkg}: {v or 'not installed'}", file=out)

    print("pip freeze:", file=out)
    print(_pip_freeze(full_freeze), file=out)

    if not ffmpeg.path or not colmap.path:
        print("Missing required binaries (ffmpeg/colmap).", file=err)
        return 1
    if not ffmpeg.ok or not colmap.ok:
        print("Binary probe failed (non-zero exit).", file=err)
        return 1
    return 0
