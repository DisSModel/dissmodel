"""
tests/io/test_convert.py
=========================
Tests for dissmodel.io.convert — vector_to_raster_backend.

Covers: GeoDataFrame and file-path sources, attrs as list and dict,
mask band, nodata_value sentinel, CRS validation/reprojection,
error paths, and the deprecated shapefile_to_raster_backend alias.
"""
from __future__ import annotations

import numpy as np
import pytest

gpd = pytest.importorskip("geopandas")
pytest.importorskip("rasterio")

from shapely.geometry import Polygon  # noqa: E402

from dissmodel.io.convert import (  # noqa: E402
    vector_to_raster_backend,
    shapefile_to_raster_backend,
)


@pytest.fixture
def gdf():
    """Two unit squares side by side covering x∈[0,2], y∈[0,1]."""
    geoms = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
    ]
    return gpd.GeoDataFrame(
        {"uso": [1, 2], "alt": [0.25, 0.75]},
        geometry=geoms,
        crs="EPSG:31984",
    )


class TestVectorToRasterBackend:

    def test_grid_dimensions_follow_bounds_and_resolution(self, gdf):
        b = vector_to_raster_backend(gdf, resolution=0.5, attrs=["uso"])
        # bounds 2x1, resolution 0.5 → 4 cols × 2 rows
        assert b.shape == (2, 4)

    def test_integer_column_rasterized_as_int32(self, gdf):
        b = vector_to_raster_backend(gdf, resolution=0.5, attrs=["uso"])
        arr = b.arrays["uso"]
        assert arr.dtype == np.int32
        # Left half burned with 1, right half with 2
        assert np.all(arr[:, :2] == 1)
        assert np.all(arr[:, 2:] == 2)

    def test_float_column_rasterized_as_float32(self, gdf):
        b = vector_to_raster_backend(gdf, resolution=0.5, attrs=["alt"])
        arr = b.arrays["alt"]
        assert arr.dtype == np.float32
        np.testing.assert_allclose(arr[:, :2], 0.25)
        np.testing.assert_allclose(arr[:, 2:], 0.75)

    def test_mask_band_added_by_default(self, gdf):
        b = vector_to_raster_backend(gdf, resolution=0.5, attrs=["uso"])
        assert "mask" in b.arrays
        assert np.all(b.arrays["mask"] == 1.0)  # fully covered extent

    def test_add_mask_false_omits_band(self, gdf):
        b = vector_to_raster_backend(
            gdf, resolution=0.5, attrs=["uso"], add_mask=False
        )
        assert "mask" not in b.arrays

    def test_attrs_dict_with_per_column_defaults(self, gdf):
        b = vector_to_raster_backend(
            gdf, resolution=0.5, attrs={"uso": -1, "alt": -9999.0}
        )
        assert set(b.arrays) >= {"uso", "alt"}

    def test_nodata_value_sentinel_outside_coverage(self):
        # Two squares at opposite corners of a 2x2 extent — the other two
        # corner cells of the grid fall outside any geometry.
        gdf2 = gpd.GeoDataFrame(
            {"uso": [5, 7]},
            geometry=[
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1.9, 1.9), (2, 1.9), (2, 2), (1.9, 2)]),
            ],
            crs="EPSG:31984",
        )
        b = vector_to_raster_backend(
            gdf2, resolution=1.0, attrs=["uso"], nodata_value=-1
        )
        arr = b.arrays["uso"]
        mask = b.arrays["mask"].astype(bool)
        assert np.all(arr[~mask] == -1)        # sentinel outside coverage
        assert b.nodata_value == -1

    def test_source_gdf_is_not_mutated(self, gdf):
        original_crs = gdf.crs
        vector_to_raster_backend(gdf, resolution=0.5, attrs=["uso"], crs="EPSG:4326")
        assert gdf.crs == original_crs

    def test_reprojection_applied_when_crs_given(self, gdf):
        b = vector_to_raster_backend(
            gdf, resolution=0.00001, attrs=["uso"], crs="EPSG:4326"
        )
        assert b.crs is not None
        assert "4326" in str(b.crs)

    def test_file_path_source(self, gdf, tmp_path):
        path = tmp_path / "grid.gpkg"
        gdf.to_file(str(path), driver="GPKG")
        b = vector_to_raster_backend(str(path), resolution=0.5, attrs=["uso"])
        assert b.shape == (2, 4)

    # ── error paths ───────────────────────────────────────────────────────────

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            vector_to_raster_backend(
                str(tmp_path / "missing.shp"), resolution=1, attrs=["uso"]
            )

    def test_empty_attrs_raises(self, gdf):
        with pytest.raises(ValueError, match="must not be empty"):
            vector_to_raster_backend(gdf, resolution=0.5, attrs=[])

    def test_missing_column_raises(self, gdf):
        with pytest.raises(ValueError, match="not found"):
            vector_to_raster_backend(gdf, resolution=0.5, attrs=["inexistente"])

    def test_no_crs_anywhere_raises(self, gdf):
        # Build a GeoDataFrame without CRS from scratch — overriding
        # .crs on an existing one is deprecated by pandas/geopandas.
        naked = gpd.GeoDataFrame(
            gdf.drop(columns="geometry"),
            geometry=list(gdf.geometry),    # raw shapely geoms — no CRS
        )
        assert naked.crs is None
        with pytest.raises(ValueError, match="no CRS"):
            vector_to_raster_backend(naked, resolution=0.5, attrs=["uso"])

    def test_gdf_without_crs_but_explicit_crs_ok(self, gdf):
        naked = gdf.copy()
        naked = naked.set_crs("EPSG:31984", allow_override=True)
        b = vector_to_raster_backend(
            naked, resolution=0.5, attrs=["uso"], crs="EPSG:31984"
        )
        assert b.shape == (2, 4)


class TestDeprecatedAlias:

    def test_shapefile_to_raster_backend_warns(self, gdf):
        with pytest.warns(FutureWarning, match="deprecated"):
            b = shapefile_to_raster_backend(gdf, resolution=0.5, attrs=["uso"])
        assert b.shape == (2, 4)