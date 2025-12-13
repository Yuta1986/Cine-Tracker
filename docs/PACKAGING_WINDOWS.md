# Sprint 3 — Windows Packaging Plan (PyInstaller)

Target: ship a standalone Windows executable bundling:
- Python + our `cinetracker` package
- External binaries: `colmap.exe` (+ required DLLs) and `ffmpeg.exe` (+ DLLs if needed)

## Proposed packaged directory layout

When built with PyInstaller (one-folder mode):

```
CineTracker/
  Windows_CineTracker.exe
  _internal/
    cinetracker/                (our python package)
    PySide6/                    (Qt)
    numpy/                      (core deps)
    third_party/
      bin/
        colmap.exe
        *.dll                    (all DLLs shipped with COLMAP release)
        ffmpeg.exe
        ffprobe.exe
```

Runtime resolution policy:
- The app sets `COLMAP_BIN` and `FFMPEG_BIN` to the bundled `_internal/third_party/bin/*` at startup.
  - Implementation: `cinetracker.runtime.configure_bundled_binaries()` (also used as a PyInstaller runtime hook).

## Notes
- COLMAP Windows CUDA release ships `colmap.exe` and a set of DLLs that must be placed adjacent to it.
- FFmpeg Windows builds may be static or may require DLLs; bundle them similarly.

## Automated fetching
The Windows build helper can download the required external binaries into `third_party/bin`:
- COLMAP: `scripts/fetch_colmap_windows_cuda.py` (invoked by `build_windows.bat --fetch-colmap`)
- FFmpeg: `scripts/fetch_ffmpeg_windows.py` (invoked by `build_windows.bat --fetch-ffmpeg`)
