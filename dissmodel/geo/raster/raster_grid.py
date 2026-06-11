"""
dissmodel/geo/raster_grid.py
=============================
Utilitário para criar RasterBackend sintético.

Análogo a vector_grid() (GeoDataFrame), mas para o substrato NumPy.

Uso
---
    from dissmodel.geo.raster_grid import raster_grid
    import numpy as np

    # grade vazia com arrays zerados
    b = raster_grid(rows=50, cols=50, attrs={"state": 0})

    # grade com array inicial customizado
    b = raster_grid(
        rows=50, cols=50,
        attrs={"state": np.random.randint(0, 2, (50, 50))}
    )
"""
from __future__ import annotations

from typing import Union

import numpy as np

from dissmodel.geo.raster.backend import RasterBackend

# Valor escalar ou array pré-computado
AttrValue = Union[int, float, np.ndarray]


def raster_grid(
    rows:  int,
    cols:  int,
    attrs: dict[str, AttrValue] | None = None,
    dtype: np.dtype | None             = None,
) -> RasterBackend:
    """
    Create a RasterBackend with optional pre-filled arrays.

    Analogous to :func:`~dissmodel.geo.vector_grid` for the raster
    substrate. Useful for tests, examples, and synthetic benchmarks.

    Parameters
    ----------
    rows : int
        Number of rows in the grid.
    cols : int
        Number of columns in the grid.
    attrs : dict, optional
        Mapping of array name → initial value.
        - scalar (int or float): fills the entire grid with that value.
        - np.ndarray of shape (rows, cols): used directly (a copy is stored).
        If not provided, an empty backend is returned.
    dtype : numpy dtype, optional
        Default dtype for scalar-initialized arrays. If None, inferred
        from the scalar type (int → np.int32, float → np.float64).

    Returns
    -------
    RasterBackend
        Backend with shape (rows, cols) and the requested arrays.

    Examples
    --------
    >>> b = raster_grid(10, 10, attrs={"state": 0})
    >>> b.shape
    (10, 10)
    >>> b.get("state").shape
    (10, 10)

    >>> import numpy as np
    >>> state = np.random.randint(0, 2, (10, 10))
    >>> b = raster_grid(10, 10, attrs={"state": state})
    """
    b = RasterBackend(shape=(rows, cols))

    for name, value in (attrs or {}).items():
        if isinstance(value, np.ndarray):
            if value.shape != (rows, cols):
                raise ValueError(
                    f"Array '{name}' has shape {value.shape}, "
                    f"expected ({rows}, {cols})."
                )
            b.set(name, value)
        else:
            # scalar → infer dtype
            if dtype is not None:
                arr_dtype = dtype
            elif isinstance(value, float):
                arr_dtype = np.dtype(np.float64)
            else:
                arr_dtype = np.dtype(np.int32)
            b.set(name, np.full((rows, cols), value, dtype=arr_dtype))

    return b
