"""
dissmodel/geo/raster/model.py
==============================
Base class for models backed by RasterBackend (NumPy 2D arrays).

Analogous to ``SpatialModel`` for the raster substrate — provides
infrastructure without imposing a transition rule contract.

Class hierarchy
---------------
    Model  (dissmodel.core)
      ├── SpatialModel     GeoDataFrame + Queen/Rook neighbourhood  (vector)
      └── RasterModel      RasterBackend + shift2d                  (raster)  ← this file
            ├── FloodRasterModel
            └── MangroveRasterModel

Usage
-----
    class MyRasterModel(RasterModel):
        def setup(self, backend, my_param=1.0):
            super().setup(backend)
            self.my_param = my_param

        def execute(self):
            uso = self.backend.get("uso").copy()
            ...
            self.backend.arrays["uso"] = new_uso
"""
from __future__ import annotations

from dissmodel.core import Model
from dissmodel.geo.raster.backend import RasterBackend, DIRS_MOORE


class RasterModel(Model):
    """
    Model backed by a RasterBackend.

    Subclass of ``Model`` that adds raster infrastructure without imposing
    a transition rule contract. Can be subclassed directly by any model
    that operates on NumPy 2D arrays.

    Parameters (setup)
    ------------------
    backend : RasterBackend
        Backend shared across all models in the same ``Environment``.

    Attributes available in subclasses
    ------------------------------------
    backend : RasterBackend
        The shared array store.
    shape : tuple[int, int]
        Grid shape ``(rows, cols)`` — shortcut for ``self.backend.shape``.
    shift : callable
        Shortcut for ``RasterBackend.shift2d`` (static method).
    dirs : list[tuple[int, int]]
        ``DIRS_MOORE`` — the 8 directions of the Moore neighbourhood.

    Examples
    --------
    >>> class HeatDiffusion(RasterModel):
    ...     def execute(self):
    ...         temp = self.backend.get("temp").copy()
    ...         for dr, dc in self.dirs:
    ...             temp += 0.1 * self.shift(temp, dr, dc)
    ...         self.backend.arrays["temp"] = temp
    """

    # Narrowing the base Model.setup(**kwargs) contract is intentional:
    # Model.__init__ forwards extra kwargs to setup, and each component
    # declares the keywords it accepts.
    def setup(self, backend: RasterBackend) -> None:  # type: ignore[override]
        self.backend = backend
        self.shape   = backend.shape
        self.shift   = RasterBackend.shift2d
        self.dirs    = DIRS_MOORE