from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from typing import Iterable, Mapping

from PySide6.QtCore import QObject, QThread, Signal

from cinetracker.ui.progress import ProgressUpdate, parse_colmap_progress


@dataclass(frozen=True)
class ProcessSpec:
    label: str
    argv: list[str]
    cwd: str | None = None
    env: Mapping[str, str] | None = None


class PipelineWorker(QObject):
    log_line = Signal(str)
    progress = Signal(int, str)  # percent, message
    finished = Signal(bool, str)  # ok, message

    def __init__(self, specs: Iterable[ProcessSpec]):
        super().__init__()
        self._specs = list(specs)
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            for spec in self._specs:
                if self._stop.is_set():
                    self.finished.emit(False, "Canceled")
                    return
                ok = self._run_one(spec)
                if not ok:
                    return
            self.finished.emit(True, "Done")
        except Exception as e:  # pragma: no cover
            self.finished.emit(False, f"Worker error: {e}")

    def _run_one(self, spec: ProcessSpec) -> bool:
        self.progress.emit(0, spec.label)
        self.log_line.emit(f"$ {' '.join(spec.argv)}")

        proc = subprocess.Popen(
            spec.argv,
            cwd=spec.cwd,
            env=None if spec.env is None else dict(spec.env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        stage = spec.label
        assert proc.stdout is not None
        for line in proc.stdout:
            if self._stop.is_set():
                proc.terminate()
                self.finished.emit(False, "Canceled")
                return False
            line = line.rstrip("\n")
            self.log_line.emit(line)
            upd = parse_colmap_progress(line, stage=stage)
            if upd:
                if upd.total > 0:
                    self.progress.emit(upd.percent, f"{upd.stage}: {upd.current}/{upd.total}")
                else:
                    self.progress.emit(0, f"{upd.stage}: {upd.current}")

        rc = proc.wait()
        if rc != 0:
            self.finished.emit(False, f"{spec.label} failed (exit {rc})")
            return False
        self.progress.emit(100, f"{spec.label}: complete")
        return True


class WorkerThread(QThread):
    def __init__(self, worker: PipelineWorker):
        super().__init__()
        self._worker = worker

    def run(self) -> None:
        self._worker.run()

