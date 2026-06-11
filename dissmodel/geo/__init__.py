# dissmodel/geo/__init__.py

# vector substrate
from .vector.neighborhood import attach_neighbors
from .vector.vector_grid import vector_grid, parse_idx
from .vector.fill import fill, FillStrategy
from .vector.cellular_automaton import CellularAutomaton
from .vector.spatial_model import SpatialModel
from .vector.sync_model import SyncSpatialModel

# raster substrate
from .raster.backend import RasterBackend, DIRS_MOORE, DIRS_VON_NEUMANN
from .raster.raster_model import RasterModel
from .raster.cellular_automaton import RasterCellularAutomaton
from .raster.raster_grid import raster_grid
from .raster.band_spec import BandSpec
from .raster.sync_model import SyncRasterModel

# raster io — opcional, não importa por padrão (requer rasterio)
# from .raster.io import load_geotiff, save_geotiff

__all__ = [
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
