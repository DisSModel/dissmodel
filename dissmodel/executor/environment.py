"""
Description of the machine and libraries that took part in a run.

Stored in ``record.metrics["environment"]`` so that a later comparison can
say *why* two outputs differ (a different GDAL build, another architecture),
not only *that* they do. Every key is always present; a library that is not
installed is recorded as ``None``.
"""
from __future__ import annotations

import importlib.metadata
import platform
import sys

RECORDED_DISTRIBUTIONS = (
    "dissmodel", "disscube", "disslucc", "numpy", "rasterio", "shapely",
    "pyproj", "geopandas", "xarray",
)


def executor_module_name(executor_cls) -> str:
    """
    Module that defines the executor. A ``python -m pkg.mod`` run reports
    ``__main__``; its real name is in ``__main__.__spec__``. A plain script
    (``python file.py``) stays ``__main__``: there is no module to import.
    """
    name = executor_cls.__module__
    if name == "__main__":
        spec = getattr(sys.modules.get("__main__"), "__spec__", None)
        if spec is not None and getattr(spec, "name", None):
            return spec.name
    return name


def _distribution_of(executor_cls) -> str | None:
    """Name of the installed distribution that provides the executor's module."""
    top = executor_module_name(executor_cls).split(".", 1)[0]
    dists = importlib.metadata.packages_distributions().get(top, [])
    return dists[0] if dists else None


def _native_libraries() -> dict[str, str | None]:
    """GDAL, GEOS and PROJ versions as reported by the Python bindings."""
    libs: dict[str, str | None] = {"gdal": None, "geos": None, "proj": None}
    try:
        import rasterio
        libs["gdal"] = getattr(rasterio, "__gdal_version__", None)
    except Exception:  # noqa: BLE001 — optional dependency
        pass
    try:
        import shapely
        libs["geos"] = getattr(shapely, "geos_version_string", None)
    except Exception:  # noqa: BLE001
        pass
    try:
        import pyproj
        libs["proj"] = getattr(pyproj, "proj_version_str", None)
    except Exception:  # noqa: BLE001
        pass
    return libs


def environment(executor_cls=None) -> dict:
    """Python, machine, native libraries and package versions of this process."""
    names = list(RECORDED_DISTRIBUTIONS)
    dist = _distribution_of(executor_cls) if executor_cls is not None else None
    if dist and dist not in names:
        names.append(dist)

    packages: dict[str, str] = {}
    for name in names:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue

    return {
        "python":           platform.python_version(),
        "platform":         sys.platform,
        "machine":          platform.machine(),
        "executor":         (f"{executor_module_name(executor_cls)}.{executor_cls.__qualname__}"
                             if executor_cls is not None else None),
        "executor_package": dist,
        "native":           _native_libraries(),
        "packages":         packages,
    }
