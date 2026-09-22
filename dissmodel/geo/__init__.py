# dissmodel/geo/__init__.py

# vector substrate
# raster substrate
from .raster.backend import DIRS_MOORE, DIRS_VON_NEUMANN, RasterBackend
from .raster.band_spec import BandSpec
from .raster.cellular_automaton import RasterCellularAutomaton
from .raster.raster_grid import raster_grid
from .raster.raster_model import RasterModel
from .raster.sync_model import SyncRasterModel
from .vector.cellular_automaton import CellularAutomaton
from .vector.fill import FillStrategy, fill
from .vector.neighborhood import attach_neighbors
from .vector.spatial_model import SpatialModel
from .vector.sync_model import SyncSpatialModel
from .vector.vector_grid import parse_idx, vector_grid

# raster io — opcional, não importa por padrão (requer rasterio)
# from .raster.io import load_geotiff, save_geotiff

__all__ = [  # noqa: RUF022 — grouped by substrate (vector, then raster), not alphabetized
    # vector
    "attach_neighbors",
    "vector_grid",
    "parse_idx",
    "fill",
    "FillStrategy",
    "CellularAutomaton",
    "SpatialModel",
    "SyncSpatialModel",
    # raster
    "RasterBackend",
    "DIRS_MOORE",
    "DIRS_VON_NEUMANN",
    "RasterModel",
    "RasterCellularAutomaton",
    "raster_grid",
    "BandSpec",
    "SyncRasterModel",
]
