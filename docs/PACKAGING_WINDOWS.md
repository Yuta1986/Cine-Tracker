# Sprint 3 — Windows Packaging Plan (PyInstaller)

Target: ship a standalone Windows executable bundling:
- Python + our `cinetracker` package
- External binaries: `colmap.exe` (+ required DLLs) and `ffmpeg.exe` (+ DLLs if needed)

## Proposed packaged directory layout

When built with PyInstaller (one-folder mode):

```
CineTracker/
  CineTracker.exe
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

## Notes
- COLMAP Windows CUDA release ships `colmap.exe` and a set of DLLs that must be placed adjacent to it.
- FFmpeg Windows builds may be static or may require DLLs; bundle them similarly.

