"""
tests/raster/test_backend_xarray.py
=====================================
Tests for RasterBackend ↔ xarray interoperability.

Requires: xarray (mandatory), rasterio + pyproj (optional — skipped if absent).
Run alongside test_backend.py — does not duplicate existing coverage.
"""
from __future__ import annotations

import numpy as np
import pytest

xr = pytest.importorskip("xarray", reason="xarray not installed")

from dissmodel.geo.raster.backend import RasterBackend


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def simple_backend():
    """3×4 backend with two bands and no transform/CRS."""
    b = RasterBackend(shape=(3, 4))
    b.set("uso",  np.array([[1, 2, 3, 4],
                             [5, 6, 7, 8],
                             [9, 0, 1, 2]], dtype=np.int8))
    b.set("alt",  np.array([[0.1, 0.2, 0.3, 0.4],
                             [0.5, 0.6, 0.7, 0.8],
                             [0.9, 1.0, 1.1, 1.2]], dtype=np.float32))
    return b


@pytest.fixture
def masked_backend():
    """3×3 backend with explicit mask band."""
    b = RasterBackend(shape=(3, 3), nodata_value=0)
    b.set("uso",  np.array([[1, 2, 0],
                             [3, 4, 0],
                             [0, 0, 0]], dtype=np.int8))
    b.set("mask", np.array([[1, 1, 0],
                             [1, 1, 0],
                             [0, 0, 0]], dtype=np.int8))
    return b


# ── to_xarray ────────────────────────────────────────────────────────────────

class TestToXarray:

    def test_returns_dataset(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert isinstance(ds, xr.Dataset)

    def test_all_bands_present(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert "uso" in ds
        assert "alt" in ds

    def test_dimensions_are_y_x(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert ds["uso"].dims == ("y", "x")
        assert ds["alt"].dims == ("y", "x")

    def test_shape_preserved(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert ds["uso"].shape == (3, 4)

    def test_values_preserved(self, simple_backend):
        ds = simple_backend.to_xarray()
        np.testing.assert_array_equal(
            ds["uso"].values, simple_backend.get("uso")
        )
        np.testing.assert_array_almost_equal(
            ds["alt"].values, simple_backend.get("alt")
        )

    def test_coords_y_x_present(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert "y" in ds.coords
        assert "x" in ds.coords
        assert len(ds.coords["y"]) == 3
        assert len(ds.coords["x"]) == 4

    def test_time_coord_absent_by_default(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert "time" not in ds.coords

    def test_time_coord_present_when_given(self, simple_backend):
        ds = simple_backend.to_xarray(time=42)
        assert "time" in ds.coords
        assert ds.coords["time"].item() == 42

    def test_cf_conventions_attr(self, simple_backend):
        ds = simple_backend.to_xarray()
        assert ds.attrs.get("Conventions") == "CF-1.8"

    def test_mask_band_exported(self, masked_backend):
        ds = masked_backend.to_xarray()
        assert "mask" in ds

    def test_independent_copy(self, simple_backend):
        """Mutating the backend after to_xarray() must not affect the Dataset."""
        ds = simple_backend.to_xarray()
        simple_backend.arrays["uso"][:] = 99
        assert ds["uso"].values[0, 0] != 99


# ── from_xarray ───────────────────────────────────────────────────────────────

class TestFromXarray:

    def test_roundtrip_values(self, simple_backend):
        ds = simple_backend.to_xarray()
        b2 = RasterBackend.from_xarray(ds)
        np.testing.assert_array_equal(b2.get("uso"), simple_backend.get("uso"))
        np.testing.assert_array_almost_equal(b2.get("alt"), simple_backend.get("alt"))

    def test_roundtrip_shape(self, simple_backend):
        ds = simple_backend.to_xarray()
        b2 = RasterBackend.from_xarray(ds)
        assert b2.shape == simple_backend.shape

    def test_band_names_preserved(self, simple_backend):
        ds = simple_backend.to_xarray()
        b2 = RasterBackend.from_xarray(ds)
        assert set(b2.band_names()) == {"uso", "alt"}

    def test_accepts_dataarray(self, simple_backend):
        """from_xarray() must accept a DataArray, wrapping it as a Dataset."""
        da = simple_backend.to_xarray()["uso"]
        da.name = "uso"
        b2 = RasterBackend.from_xarray(da)
        assert "uso" in b2.band_names()
        np.testing.assert_array_equal(b2.get("uso"), simple_backend.get("uso"))

    def test_dataarray_unnamed_falls_back_to_data(self, simple_backend):
        da = simple_backend.to_xarray()["uso"].rename(None)
        b2 = RasterBackend.from_xarray(da)
        assert "data" in b2.band_names()

    def test_skips_scalar_variables(self, simple_backend):
        """spatial_ref and other scalars must not appear as bands."""
        ds = simple_backend.to_xarray()
        # inject a fake scalar variable
        ds = ds.assign(scalar_var=xr.DataArray(0))
        b2 = RasterBackend.from_xarray(ds)
        assert "scalar_var" not in b2.band_names()

    def test_no_spatial_vars_raises(self):
        ds = xr.Dataset({"scalar": xr.DataArray(42)})
        with pytest.raises(ValueError, match="No spatial"):
            RasterBackend.from_xarray(ds)

    def test_nodata_value_forwarded(self, simple_backend):
        ds = simple_backend.to_xarray()
        b2 = RasterBackend.from_xarray(ds, nodata_value=-1)
        assert b2.nodata_value == -1

    def test_independent_copy(self, simple_backend):
        """Mutating the Dataset after from_xarray() must not affect the backend."""
        ds = simple_backend.to_xarray()
        b2 = RasterBackend.from_xarray(ds)
        ds["uso"].values[0, 0] = 99
        assert b2.get("uso")[0, 0] != 99


# ── rename_band ───────────────────────────────────────────────────────────────

class TestRenameBand:

    def test_rename_exists(self, simple_backend):
        simple_backend.rename_band("uso", "land_use")
        assert "land_use" in simple_backend.arrays
        assert "uso" not in simple_backend.arrays

    def test_rename_preserves_values(self, simple_backend):
        original = simple_backend.get("uso").copy()
        simple_backend.rename_band("uso", "land_use")
        np.testing.assert_array_equal(simple_backend.get("land_use"), original)

    def test_rename_missing_is_noop(self, simple_backend):
        # should not raise
        simple_backend.rename_band("nonexistent", "whatever")
        assert "whatever" not in simple_backend.arrays

    def test_rename_does_not_affect_other_bands(self, simple_backend):
        alt_before = simple_backend.get("alt").copy()
        simple_backend.rename_band("uso", "land_use")
        np.testing.assert_array_equal(simple_backend.get("alt"), alt_before)


# ── optional: transform recovery (rasterio) ───────────────────────────────────

try:
    import rasterio as _rasterio  # noqa: F401
    _HAS_RASTERIO = True
except ImportError:
    _HAS_RASTERIO = False


class TestTransformRecovery:

    @pytest.mark.skipif(not _HAS_RASTERIO, reason="rasterio not installed")
    def test_pixel_index_coords_when_no_transform(self, simple_backend):
        """Without transform, coords must be integer pixel indices."""
        ds = simple_backend.to_xarray()
        np.testing.assert_array_equal(ds.coords["x"].values, [0.0, 1.0, 2.0, 3.0])
        np.testing.assert_array_equal(ds.coords["y"].values, [0.0, 1.0, 2.0])
