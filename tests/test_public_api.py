"""
tests/test_public_api.py
=========================
Smoke tests for the documented public import paths.

Every import below appears in the README or in module docstrings; this
suite guarantees the shortcuts stay importable (they failed on develop
before the geo/raster and geo/vector re-exports were added).
"""
from __future__ import annotations


class TestCoreImports:

    def test_core(self):
        from dissmodel.core import Environment, Model  # noqa: F401


class TestGeoTopLevelImports:

    def test_geo_shortcuts(self):
        from dissmodel.geo import (  # noqa: F401
            CellularAutomaton,
            FillStrategy,
            RasterBackend,
            RasterCellularAutomaton,
            RasterModel,
            SpatialModel,
            SyncRasterModel,
            SyncSpatialModel,
            attach_neighbors,
            fill,
            raster_grid,
            vector_grid,
        )


class TestGeoRasterImports:

    def test_raster_backend(self):
        from dissmodel.geo.raster import (  # noqa: F401
            DIRS_MOORE,
            DIRS_VON_NEUMANN,
            RasterBackend,
        )

    def test_raster_models_and_helpers(self):
        from dissmodel.geo.raster import (  # noqa: F401
            BandSpec,
            RasterCellularAutomaton,
            RasterModel,
            SyncRasterModel,
            raster_grid,
        )

    def test_shortcut_is_same_object_as_module_path(self):
        from dissmodel.geo.raster import RasterBackend as short
        from dissmodel.geo.raster.backend import RasterBackend as full
        assert short is full


class TestGeoVectorImports:

    def test_vector_grid_helpers(self):
        from dissmodel.geo.vector import (  # noqa: F401
            parse_idx,
            regular_grid,
            vector_grid,
        )

    def test_vector_models(self):
        from dissmodel.geo.vector import (  # noqa: F401
            CellularAutomaton,
            SpatialModel,
            SyncSpatialModel,
        )

    def test_neighborhood_and_fill(self):
        from dissmodel.geo.vector import (  # noqa: F401
            FillStrategy,
            attach_neighbors,
            export_neighbors,
            fill,
            get_neighbor_values,
            get_neighbors,
            register_strategy,
        )

    def test_shortcut_is_same_object_as_module_path(self):
        from dissmodel.geo.vector import SpatialModel as short
        from dissmodel.geo.vector.spatial_model import SpatialModel as full
        assert short is full
