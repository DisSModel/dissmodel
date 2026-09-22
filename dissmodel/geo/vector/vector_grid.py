from __future__ import annotations

from collections import namedtuple
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import box

# Reusable type aliases
Bounds = tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)
Dimension = tuple[int, int]                 # (n_cols, n_rows)

# Named return type for parse_idx — eliminates (col, row) vs (row, col) ambiguity.
GridPos = namedtuple("GridPos", ["row", "col"])


def parse_idx(idx: str) -> GridPos:
    """
    Extract row and col from an index string in ``'row-col'`` format.

    Parameters
    ----------
    idx : str
        Index string in ``'row-col'`` format, e.g. ``'0-0'``, ``'3-4'``.

    Returns
    -------
    GridPos
        Named tuple with fields ``row`` and ``col``.

    Examples
    --------
    >>> pos = parse_idx('3-4')
    >>> pos.row
    3
    >>> pos.col
    4
    >>> row, col = parse_idx('3-4')  # tuple unpacking still works
    """
    row_str, col_str = idx.split("-")
    return GridPos(row=int(row_str), col=int(col_str))


def vector_grid(
    gdf: gpd.GeoDataFrame | None = None,
    bounds: Bounds | None = None,
    resolution: float | None = None,
    dimension: Dimension | None = None,
    attrs: dict[str, Any] | None = None,
    crs: str | int | None = None,
) -> gpd.GeoDataFrame:
    """
    Create a regular grid of fixed-size cells.

    Exactly one of the following input combinations must be provided:

    - ``dimension`` + ``resolution`` — abstract grid with no geographic location
    - ``bounds`` + ``resolution`` — grid fitted to a bounding box by cell size
    - ``bounds`` + ``dimension`` — grid fitted to a bounding box by cell count
    - ``gdf`` — bounds are extracted from the GeoDataFrame

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame, optional
        GeoDataFrame used to extract the bounding box.
    bounds : tuple of float, optional
        Bounding box as ``(xmin, ymin, xmax, ymax)``.
    resolution : float, optional
        Cell size in coordinate units.
    dimension : tuple of int, optional
        Grid shape as ``(n_cols, n_rows)``.
    attrs : dict, optional
        Extra attributes added to every cell, e.g. ``{'state': 0}``.
    crs : str or int, optional
        Coordinate reference system. If ``None``, the grid is abstract
        (no geographic location).

    Returns
    -------
    geopandas.GeoDataFrame
        Regular grid where each row is a cell with a Polygon geometry,
        indexed by ``'id'`` in ``'row-col'`` format.

    Raises
    ------
    ValueError
        If the input combination is insufficient to define the grid.

    Examples
    --------
    >>> gdf = vector_grid(dimension=(3, 3), resolution=1.0)
    >>> len(gdf)
    9
    >>> gdf.index[0]
    '0-0'
    """
    attrs = attrs or {}

    resolution_x: float
    resolution_y: float
    n_cols: int
    n_rows: int
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    if dimension is not None and resolution is not None and bounds is None and gdf is None:
        n_cols, n_rows = dimension
        xmin, ymin = 0.0, 0.0
        resolution_x = resolution_y = resolution
        xmax = xmin + n_cols * resolution_x
        ymax = ymin + n_rows * resolution_y

    elif bounds is not None:
        xmin, ymin, xmax, ymax = bounds
        width = xmax - xmin
        height = ymax - ymin

        if resolution is not None:
            resolution_x = resolution_y = resolution
            n_cols = int(np.ceil(width / resolution_x))
            n_rows = int(np.ceil(height / resolution_y))
        elif dimension is not None:
            n_cols, n_rows = dimension
            resolution_x = width / n_cols
            resolution_y = height / n_rows
        else:
            raise ValueError("Provide either `resolution` or `dimension`.")

    elif gdf is not None:
        return vector_grid(
            bounds=tuple(gdf.total_bounds),  # type: ignore[arg-type]
            resolution=resolution,
            dimension=dimension,
            attrs=attrs,
            crs=gdf.crs,
        )

    else:
        raise ValueError("Provide `gdf`, `bounds`, or `dimension` with `resolution`.")

    x_edges: np.ndarray = np.arange(xmin, xmax, resolution_x)
    y_edges: np.ndarray = np.arange(ymin, ymax, resolution_y)

    grid_cells = []
    ids = []
    for i, x0 in enumerate(x_edges):
        for j, y0 in enumerate(y_edges):
            grid_cells.append(box(x0, y0, x0 + resolution_x, y0 + resolution_y))
            ids.append(f"{j}-{i}")

    data: dict[str, Any] = {"geometry": grid_cells, "id": ids}
    for key, value in attrs.items():
        data[key] = [value] * len(grid_cells)

    return gpd.GeoDataFrame(data, crs=crs).set_index("id")


# Deprecated alias — will be removed in v0.3.0
def regular_grid(*args, **kwargs) -> gpd.GeoDataFrame:
    """Deprecated. Use :func:`vector_grid` instead."""
    import warnings
    warnings.warn(
        "regular_grid() is deprecated, use vector_grid() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return vector_grid(*args, **kwargs)