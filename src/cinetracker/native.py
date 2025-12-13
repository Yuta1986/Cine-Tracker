from __future__ import annotations


class NativeNotAvailable(RuntimeError):
    pass


def require_native():
    """
    Loads the compiled native extension module.

    Expected module name (importable):
      - `cinetracker_native` (built via pybind11 + Ceres)
    """

    try:
        import cinetracker_native  # type: ignore
    except Exception as e:  # pragma: no cover
        raise NativeNotAvailable(
            "Native extension not available. Build the C++/Ceres module and ensure `cinetracker_native` is importable."
        ) from e
    return cinetracker_native

