from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMainWindow,
    QInputDialog,
    QMessageBox,
)

from cinetracker.core.colmap_cli import COLMAP
from cinetracker.core.lens_profiles import add_profile, list_profiles, resolve_profile_json
from cinetracker.ui.worker import PipelineWorker, ProcessSpec, WorkerThread


@dataclass(frozen=True)
class UiPaths:
    colmap_bin: str
    ffmpeg_bin: str | None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cine-Tracker (Sprint 3 UI)")
        self.resize(1100, 700)

        central = QWidget(self)
        self.setCentralWidget(central)

        self._worker_thread: WorkerThread | None = None
        self._worker: PipelineWorker | None = None

        self.colmap_path = QLineEdit()
        self.colmap_path.setPlaceholderText("Path to colmap.exe (optional; uses COLMAP_BIN/third_party/bin fallback)")
        self.colmap_browse = QPushButton("Browse")
        self.colmap_browse.clicked.connect(self._browse_colmap)

        self.f01_video = QLineEdit()
        self.f01_video.setPlaceholderText("Chessboard video file (Calibration Mode)")
        self.f01_browse = QPushButton("Browse")
        self.f01_browse.clicked.connect(lambda: self._browse_file(self.f01_video))
        self.f01_out = QLineEdit("output/f01")
        self.f01_out_browse = QPushButton("Browse")
        self.f01_out_browse.clicked.connect(lambda: self._browse_dir(self.f01_out))
        self.f01_run = QPushButton("Run F-01 (Calibration)")
        self.f01_run.clicked.connect(self._run_f01)

        self.f02_video = QLineEdit()
        self.f02_video.setPlaceholderText("Main scene video file (Tracking Mode)")
        self.f02_browse = QPushButton("Browse")
        self.f02_browse.clicked.connect(lambda: self._browse_file(self.f02_video))
        self.f02_lens_json = QLineEdit()
        self.f02_lens_json.setPlaceholderText("lens_calibration_data.json (required)")
        self.f02_lens_browse = QPushButton("Browse")
        self.f02_lens_browse.clicked.connect(lambda: self._browse_file(self.f02_lens_json, filter_str="JSON (*.json)"))

        self.profile_combo = QComboBox()
        self.profile_refresh = QPushButton("Refresh")
        self.profile_refresh.clicked.connect(self._refresh_profiles)
        self.profile_use = QPushButton("Use")
        self.profile_use.clicked.connect(self._use_selected_profile)
        self.profile_save = QPushButton("Save…")
        self.profile_save.clicked.connect(self._save_profile_from_json)

        self.f02_out = QLineEdit("output/f02")
        self.f02_out_browse = QPushButton("Browse")
        self.f02_out_browse.clicked.connect(lambda: self._browse_dir(self.f02_out))
        self.f02_run = QPushButton("Run F-02 (Tracking)")
        self.f02_run.clicked.connect(self._run_f02)

        self.status = QLabel("Idle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.cancel = QPushButton("Cancel")
        self.cancel.setEnabled(False)
        self.cancel.clicked.connect(self._cancel)

        root = QVBoxLayout()
        root.addWidget(self._build_paths_box())

        top = QHBoxLayout()
        top.addWidget(self._build_f01_box(), 1)
        top.addWidget(self._build_f02_box(), 1)
        root.addLayout(top, 0)

        root.addWidget(self._build_output_box(), 2)
        central.setLayout(root)

        self._refresh_profiles()

    def _build_paths_box(self) -> QGroupBox:
        box = QGroupBox("Binaries")
        layout = QGridLayout()
        layout.addWidget(QLabel("COLMAP"), 0, 0)
        layout.addWidget(self.colmap_path, 0, 1)
        layout.addWidget(self.colmap_browse, 0, 2)
        box.setLayout(layout)
        return box

    def _build_f01_box(self) -> QGroupBox:
        box = QGroupBox("F-01 Setup (Calibration)")
        form = QFormLayout()
        row1 = QHBoxLayout()
        row1.addWidget(self.f01_video, 1)
        row1.addWidget(self.f01_browse)
        form.addRow("Video", row1)
        row_out = QHBoxLayout()
        row_out.addWidget(self.f01_out, 1)
        row_out.addWidget(self.f01_out_browse)
        form.addRow("Output Dir", row_out)
        form.addRow(self.f01_run)
        box.setLayout(form)
        return box

    def _build_f02_box(self) -> QGroupBox:
        box = QGroupBox("F-02 Setup (Tracking)")
        form = QFormLayout()
        row1 = QHBoxLayout()
        row1.addWidget(self.f02_video, 1)
        row1.addWidget(self.f02_browse)
        form.addRow("Video", row1)

        prow = QHBoxLayout()
        prow.addWidget(self.profile_combo, 1)
        prow.addWidget(self.profile_use)
        prow.addWidget(self.profile_refresh)
        prow.addWidget(self.profile_save)
        form.addRow("Lens Profile", prow)

        row2 = QHBoxLayout()
        row2.addWidget(self.f02_lens_json, 1)
        row2.addWidget(self.f02_lens_browse)
        form.addRow("Lens JSON", row2)
        row_out = QHBoxLayout()
        row_out.addWidget(self.f02_out, 1)
        row_out.addWidget(self.f02_out_browse)
        form.addRow("Output Dir", row_out)
        form.addRow(self.f02_run)
        box.setLayout(form)
        return box

    def _build_output_box(self) -> QGroupBox:
        box = QGroupBox("Output / Log")
        v = QVBoxLayout()
        row = QHBoxLayout()
        row.addWidget(self.status, 1)
        row.addWidget(self.cancel, 0, Qt.AlignRight)
        v.addLayout(row)
        v.addWidget(self.progress)
        v.addWidget(self.log, 1)
        box.setLayout(v)
        return box

    def _browse_colmap(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select colmap executable")
        if path:
            self.colmap_path.setText(path)

    def _browse_file(self, line_edit: QLineEdit, filter_str: str = "All Files (*)") -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file", filter=filter_str)
        if path:
            line_edit.setText(path)

    def _browse_dir(self, line_edit: QLineEdit) -> None:
        start = line_edit.text().strip() or str(Path.cwd())
        path = QFileDialog.getExistingDirectory(self, "Select output directory", start)
        if path:
            line_edit.setText(path)

    def _refresh_profiles(self) -> None:
        try:
            profiles = list_profiles()
        except Exception as e:
            QMessageBox.warning(self, "Lens Profiles", f"Failed to list profiles:\n{e}")
            profiles = []

        self.profile_combo.clear()
        if not profiles:
            self.profile_combo.addItem("(no saved profiles)", None)
            self.profile_use.setEnabled(False)
            return

        for prof in profiles:
            dims = (
                f"{prof.image_width}x{prof.image_height}"
                if prof.image_width is not None and prof.image_height is not None
                else "?"
            )
            model = prof.camera_model or "?"
            label = f"{prof.name}  ({model}, {dims})"
            self.profile_combo.addItem(label, prof.name)
        self.profile_use.setEnabled(True)

    def _use_selected_profile(self) -> None:
        name = self.profile_combo.currentData()
        if not name:
            return
        try:
            p = resolve_profile_json(str(name))
        except Exception as e:
            QMessageBox.warning(self, "Lens Profiles", f"Failed to resolve profile:\n{e}")
            return
        self.f02_lens_json.setText(str(p))

    def _save_profile_from_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select lens_calibration_data.json", filter="JSON (*.json)")
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Save Lens Profile", "Profile name:")
        if not ok:
            return
        try:
            add_profile(name=name, json_path=path, overwrite=False)
        except FileExistsError:
            overwrite = QMessageBox.question(
                self,
                "Lens Profiles",
                "Profile already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if overwrite != QMessageBox.StandardButton.Yes:
                return
            try:
                add_profile(name=name, json_path=path, overwrite=True)
            except Exception as e:
                QMessageBox.warning(self, "Lens Profiles", f"Failed to save profile:\n{e}")
                return
        except Exception as e:
            QMessageBox.warning(self, "Lens Profiles", f"Failed to save profile:\n{e}")
            return

        QMessageBox.information(self, "Lens Profiles", "Saved.")
        self._refresh_profiles()

    def _append_log(self, text: str) -> None:
        self.log.append(text)
        self.log.moveCursor(self.log.textCursor().End)

    def _set_running(self, running: bool) -> None:
        self.f01_run.setEnabled(not running)
        self.f02_run.setEnabled(not running)
        self.cancel.setEnabled(running)

    def _cancel(self) -> None:
        if self._worker:
            self._worker.stop()

    def _resolve_paths(self) -> UiPaths:
        colmap = COLMAP.resolve(explicit=self.colmap_path.text().strip() or None)
        return UiPaths(colmap_bin=colmap.path, ffmpeg_bin=None)

    def _start_pipeline(self, specs: list[ProcessSpec]) -> None:
        self._append_log("-----")
        worker = PipelineWorker(specs)
        thread = WorkerThread(worker)
        worker.log_line.connect(self._append_log)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_finished)

        self._worker = worker
        self._worker_thread = thread
        self.progress.setValue(0)
        self.status.setText("Running...")
        self._set_running(True)
        thread.start()

    def _on_progress(self, percent: int, message: str) -> None:
        if percent:
            self.progress.setValue(percent)
        self.status.setText(message)

    def _on_finished(self, ok: bool, message: str) -> None:
        self.status.setText(message)
        if ok:
            self.progress.setValue(100)
        self._set_running(False)
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        self._worker_thread = None
        self._worker = None

    def _run_f01(self) -> None:
        # Sprint 3: UI wiring only (pipeline steps implemented in Sprint 2 core/CLI).
        # This placeholder demonstrates the threading model and log streaming.
        paths = self._resolve_paths()
        out_dir = Path(self.f01_out.text().strip() or "output/f01")
        out_dir.mkdir(parents=True, exist_ok=True)

        specs = [
            ProcessSpec(label="COLMAP (placeholder)", argv=[paths.colmap_bin, "-h"]),
        ]
        self._start_pipeline(specs)

    def _run_f02(self) -> None:
        paths = self._resolve_paths()
        out_dir = Path(self.f02_out.text().strip() or "output/f02")
        out_dir.mkdir(parents=True, exist_ok=True)

        specs = [
            ProcessSpec(label="COLMAP (placeholder)", argv=[paths.colmap_bin, "-h"]),
        ]
        self._start_pipeline(specs)
