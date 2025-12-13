from __future__ import annotations

# Executed by PyInstaller at process start (before importing the app entrypoint).
from cinetracker.runtime import configure_bundled_binaries

configure_bundled_binaries(strict=False)

