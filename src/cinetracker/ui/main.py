from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PySide6 is required for the GUI. Install with `pip install -e .[ui]`.") from e

    from cinetracker.ui.window import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

