"""
dissmodel.geo.vector
=====================
Vector substrate: GeoDataFrame-based grids, neighborhoods and CA models.

Public shortcuts re-exported here so the documented form
``from dissmodel.geo.vector import vector_grid`` works alongside the
full module paths (``dissmodel.geo.vector.vector_grid`` etc.).
"""
from .cellular_automaton import CellularAutomaton
from .fill import FillStrategy, fill, register_strategy
from .neighborhood import (
    attach_neighbors,
    export_neighbors,
    get_neighbor_values,
    get_neighbors,
)
from .spatial_model import SpatialModel
from .sync_model import SyncSpatialModel
from .vector_grid import parse_idx, regular_grid, vector_grid

__all__ = [
    "CellularAutomaton",
    "FillStrategy",
    "fill",
    "register_strategy",
    "attach_neighbors",
    "export_neighbors",
    "get_neighbor_values",
    "get_neighbors",
    "SpatialModel",
    "SyncSpatialModel",
    "parse_idx",
    "regular_grid",
    "vector_grid",
]
