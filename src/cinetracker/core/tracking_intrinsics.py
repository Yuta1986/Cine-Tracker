from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cinetracker.core.colmap_db import inject_intrinsics_into_database


@dataclass(frozen=True)
class FixedIntrinsicsMapperArgs:
    """
    Mapper flags that prevent intrinsics changes (extrinsics-only BA).

    Note: COLMAP option names are under the `Mapper` group.
    """

    ba_refine_focal_length: int = 0
    ba_refine_principal_point: int = 0
    ba_refine_extra_params: int = 0

    def to_cli_args(self) -> list[str]:
        return [
            "--Mapper.ba_refine_focal_length",
            str(self.ba_refine_focal_length),
            "--Mapper.ba_refine_principal_point",
            str(self.ba_refine_principal_point),
            "--Mapper.ba_refine_extra_params",
            str(self.ba_refine_extra_params),
        ]


def inject_fixed_intrinsics_from_json(
    *,
    database_path: str,
    lens_json_path: str,
    camera_id: int | None = None,
    update_all: bool = False,
    dry_run: bool = False,
) -> int:
    """
    S2.2: Update COLMAP `database.db` cameras table from `lens_calibration_data.json`.

    Implementation method: raw SQLite manipulation via `sqlite3` (no PyCOLMAP dependency).
    """

    import sys

    return inject_intrinsics_into_database(
        database_path=database_path,
        json_path=lens_json_path,
        camera_id=camera_id,
        update_all=update_all,
        override_model="OPENCV",
        set_dimensions=True,
        set_prior_focal_length=True,
        dry_run=dry_run,
        out=sys.stdout,
        err=sys.stderr,
    )


def recommended_tracking_mapper_args() -> list[str]:
    """
    Canonical CLI args for Tracking Mode (F-02) to guarantee intrinsics are not optimized.
    """

    return FixedIntrinsicsMapperArgs().to_cli_args()

