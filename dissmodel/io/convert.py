# dissmodel/io/convert.py
from __future__ import annotations

import pathlib
import warnings
from typing import Any

import numpy as np

from dissmodel.geo.raster.backend import RasterBackend


def vector_to_raster_backend(
    source: str | pathlib.Path | Any,   # Any = gpd.GeoDataFrame
    resolution: float,
    attrs: list[str] | dict[str, Any],
    crs: str | int | None = None,
    all_touched: bool = False,
    nodata: int | float = 0,
    nodata_value: int | float | None = None,
    add_mask: bool = True,
) -> RasterBackend:
    """
    Convert a vector source to a RasterBackend.

    Accepts a file path (Shapefile, GeoJSON, GPKG, .zip) or an in-memory
    GeoDataFrame. Each requested attribute column is rasterized into a
    separate band.

    Parameters
    ----------
    source : str, Path, or GeoDataFrame
        Vector source. File paths are read with GeoPandas; GeoDataFrames
        are used directly (a copy is made before any reprojection).
    resolution : float
        Cell size in the units of the CRS.
    attrs : list[str] or dict[str, Any]
        Columns to rasterize. A list uses ``nodata`` as fill for all columns;
        a dict maps column names to per-column fill defaults.
    crs : str, int, or None
        Target CRS for reprojection. If ``None`` and source is a GeoDataFrame
        without a CRS, a ValueError is raised.
    all_touched : bool
        If ``True``, burn all cells touched by a geometry edge.
    nodata : int or float
        Default fill for cells outside geometries. Default: ``0``.
    nodata_value : int or float or None
        Sentinel for out-of-extent cells. Useful when ``0`` is a valid value
        (e.g. ``nodata_value=-1`` for proportion arrays). Default: ``None``.
    add_mask : bool
        If ``True`` (default), adds a ``"mask"`` band — ``1.0`` where a cell
        is covered by at least one geometry, ``0.0`` elsewhere.

    Returns
    -------
    RasterBackend

    Raises
    ------
    ImportError
        If ``geopandas`` or ``rasterio`` are not installed.
    FileNotFoundError
        If a file path does not exist.
    ValueError
        If ``attrs`` is empty, a requested column is missing, or the
        GeoDataFrame has no CRS and ``crs`` is also ``None``.

    Examples
    --------
    ```python
    # From file path
    b = vector_to_raster_backend(
        "data/mangue_grid.shp", resolution=100, attrs=["uso", "alt"]
    )

    # From in-memory GeoDataFrame
    import geopandas as gpd
    gdf = gpd.read_file("data/mangue_grid.shp").to_crs("EPSG:31984")
    b = vector_to_raster_backend(gdf, resolution=100, attrs={"uso": -1})
    ```
    """
    try:
        import rasterio
        import rasterio.features
        import rasterio.transform
    except ImportError:
        raise ImportError("rasterio is required — pip install rasterio")

    try:
        import geopandas as gpd
    except ImportError:
        raise ImportError("geopandas is required — pip install geopandas")

    # ── resolve source → GeoDataFrame ────────────────────────────────────────
    if isinstance(source, (str, pathlib.Path)):
        path = pathlib.Path(source)
        if not str(source).startswith("zip://") and not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        gdf = gpd.read_file(str(source))
    else:
        # Assume GeoDataFrame — make a copy to avoid mutating the caller's data
        gdf = source.copy()

    # ── CRS validation and reprojection ───────────────────────────────────────
    if gdf.crs is None and crs is None:
        raise ValueError(
            "Source GeoDataFrame has no CRS and no target CRS was provided. "
            "Pass crs= to specify the coordinate reference system."
        )

    if crs is not None:
        gdf = gdf.to_crs(crs)

    # ── resolve attrs → {column: fill_default} ────────────────────────────────
    if isinstance(attrs, list):
        attr_defaults: dict[str, Any] = {col: nodata for col in attrs}
    else:
        attr_defaults = dict(attrs)

    if not attr_defaults:
        raise ValueError("attrs must not be empty")

    missing = [col for col in attr_defaults if col not in gdf.columns]
    if missing:
        raise ValueError(f"Columns not found in source: {missing}")

    # ── compute grid from bounding box ────────────────────────────────────────
    xmin, ymin, xmax, ymax = gdf.total_bounds
    n_cols = int(np.ceil((xmax - xmin) / resolution))
    n_rows = int(np.ceil((ymax - ymin) / resolution))

    transform = rasterio.transform.from_bounds(
        xmin, ymin, xmax, ymax, n_cols, n_rows
    )

    backend = RasterBackend(
        shape        = (n_rows, n_cols),
        nodata_value = nodata_value,
        transform    = transform,  
        crs          = gdf.crs     
    )

    # ── rasterize geometry coverage → "mask" band ─────────────────────────────
    valid_geoms = [geom for geom in gdf.geometry if geom is not None]
    coverage = rasterio.features.rasterize(
        shapes    = ((geom, 1) for geom in valid_geoms),
        out_shape = (n_rows, n_cols),
        transform = transform,
        fill      = 0,
        all_touched = all_touched,
        dtype     = np.uint8,
    )
    mask = coverage.astype(bool)

    if add_mask:
        backend.set("mask", mask.astype(np.float32))

    # ── rasterize each attribute column ───────────────────────────────────────
    for col, default in attr_defaults.items():
        values = gdf[col]

        dtype = np.int32 if np.issubdtype(values.dtype, np.integer) else np.float32

        arr = rasterio.features.rasterize(
            shapes = (
                (geom, float(val))
                for geom, val in zip(gdf.geometry, values)
                if geom is not None
            ),
            out_shape = (n_rows, n_cols),
            transform = transform,
            fill      = float(default),
            all_touched = all_touched,
            dtype     = dtype,
        )

        sentinel = nodata_value if nodata_value is not None else default
        arr = np.where(mask, arr, sentinel).astype(dtype)
        backend.set(col, arr)

    n_valid = int(mask.sum())
    n_total = n_rows * n_cols
    print(
        f"  rasterized: {n_valid:,} valid cells"
        f" / {n_total:,} total"
        f" ({100 * n_valid / n_total:.1f}% coverage)"
    )

    return backend


def shapefile_to_raster_backend(*args, **kwargs) -> RasterBackend:
    """
    Deprecated alias for vector_to_raster_backend.
    Use vector_to_raster_backend instead.
    """
    warnings.warn(
        "shapefile_to_raster_backend is deprecated and will be removed in a "
        "future version. Use vector_to_raster_backend instead.",
        FutureWarning,
        stacklevel=2,
    )
    return vector_to_raster_backend(*args, **kwargs)