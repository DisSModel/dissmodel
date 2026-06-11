"""
dissmodel.geo.raster
=====================
Raster substrate: NumPy-backed grid storage and vectorized CA operations.

Public shortcuts re-exported here so the documented form
``from dissmodel.geo.raster import RasterBackend`` works alongside the
full module paths (``dissmodel.geo.raster.backend`` etc.).
"""
from .backend import DIRS_MOORE, DIRS_VON_NEUMANN, RasterBackend
from .band_spec import BandSpec
from .cellular_automaton import RasterCellularAutomaton
from .raster_grid import raster_grid
from .raster_model import RasterModel
from .sync_model import SyncRasterModel

__all__ = [
    "DIRS_MOORE",
    "DIRS_VON_NEUMANN",
    "RasterBackend",
    "BandSpec",
    "RasterCellularAutomaton",
    "raster_grid",
    "RasterModel",
    "SyncRasterModel",
]
