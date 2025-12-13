from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressUpdate:
    stage: str
    current: int
    total: int

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return max(0, min(100, int(round(100 * (self.current / self.total)))))


_PROCESSED_FILE_RE = re.compile(r"Processed file\s*\[(\d+)\s*/\s*(\d+)\]", re.IGNORECASE)
_REGISTERING_IMAGE_RE = re.compile(r"Registering image\s*#(\d+)\s*\(num_reg_frames=(\d+)\)", re.IGNORECASE)


def parse_colmap_progress(line: str, *, stage: str) -> ProgressUpdate | None:
    """
    Best-effort progress parsing from COLMAP console output.
    """

    m = _PROCESSED_FILE_RE.search(line)
    if m:
        cur, total = int(m.group(1)), int(m.group(2))
        return ProgressUpdate(stage=stage, current=cur, total=total)

    # Mapper doesn't always expose total, but we can surface "registered frames" as pseudo-progress.
    m = _REGISTERING_IMAGE_RE.search(line)
    if m:
        reg = int(m.group(2))
        return ProgressUpdate(stage=stage, current=reg, total=0)

    return None
