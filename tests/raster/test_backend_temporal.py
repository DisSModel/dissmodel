"""
tests/raster/test_backend_temporal.py
======================================
Tests for the temporal ``(time, y, x)`` variable API of ``RasterBackend``.

This API is the integration substrate for DisSCube: ``CubeClient.to_lucc_data()``
calls ``backend.set(name, arr, time=time_coords)`` and CA models call
``backend.get(name, time=step)`` every tick, so the contract pinned here is
a public interface between the two packages.

Time lookup rule (pinned by ``TestCeilingLookup``): ``get(name, time=t)``
uses ``np.searchsorted(axis, t)`` (side='left') with the index clamped to
``[0, len(axis) - 1]`` — i.e. a *ceiling* lookup: an exact match returns
that slice; a value between coordinates returns the next (later) slice;
values outside the axis clamp to the first/last slice without raising.

Only the xarray interop classes require xarray; everything else is pure NumPy.
"""
from __future__ import annotations

import numpy as np
import pytest

from dissmodel.geo.raster.backend import RasterBackend

try:
    import xarray as xr
    _HAS_XARRAY = True
except ImportError:
    _HAS_XARRAY = False

requires_xarray = pytest.mark.skipif(not _HAS_XARRAY, reason="xarray not installed")


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def arr_3d():
    """(3, 3, 4) array where every cell of slice i holds the value i."""
    return np.stack([np.full((3, 4), i, dtype=np.int8) for i in range(3)])


@pytest.fixture
def temporal_backend(arr_3d):
    """Backend with one temporal ('dist_roads') and one static ('slope') var."""
    b = RasterBackend(shape=(3, 4))
    b.set("dist_roads", arr_3d, time=[2000, 2010, 2020])
    b.set("slope", np.arange(12, dtype=float).reshape(3, 4))
    return b


# ── 1. temporal set/get round-trip ────────────────────────────────────────────

class TestTemporalRoundTrip:

    def test_is_temporal_true(self, temporal_backend):
        assert temporal_backend.is_temporal("dist_roads") is True

    def test_time_axis_equals_given_coords(self, temporal_backend):
        np.testing.assert_array_equal(
            temporal_backend.time_axis("dist_roads"), [2000, 2010, 2020]
        )

    def test_get_without_time_returns_full_series(self, temporal_backend, arr_3d):
        full = temporal_backend.get("dist_roads")
        assert full.shape == (3, 3, 4)
        np.testing.assert_array_equal(full, arr_3d)

    def test_get_with_exact_time_returns_2d_slice(self, temporal_backend, arr_3d):
        sl = temporal_backend.get("dist_roads", time=2010)
        assert sl.shape == (3, 4)
        np.testing.assert_array_equal(sl, arr_3d[1])

    def test_set_stores_a_copy(self, arr_3d):
        b = RasterBackend(shape=(3, 4))
        b.set("v", arr_3d, time=[2000, 2010, 2020])
        arr_3d[:] = 99
        assert b.get("v", time=2000)[0, 0] == 0

    def test_time_accepts_ndarray(self, arr_3d):
        b = RasterBackend(shape=(3, 4))
        b.set("v", arr_3d, time=np.array([2000, 2010, 2020]))
        assert b.is_temporal("v")
        np.testing.assert_array_equal(b.time_axis("v"), [2000, 2010, 2020])


# ── 2. nearest-time lookup rule ───────────────────────────────────────────────

class TestCeilingLookup:
    """
    The lookup is a CEILING rule, not nearest: np.searchsorted(axis, t)
    returns the insertion point, so a time between two coordinates selects
    the next (later) slice. The index is then clamped, so out-of-range
    times return the first/last slice instead of raising IndexError.
    """

    def test_between_coords_returns_next_slice(self, temporal_backend, arr_3d):
        # 2005 ∈ (2000, 2010) → ceiling → slice at 2010 (index 1)
        sl = temporal_backend.get("dist_roads", time=2005)
        np.testing.assert_array_equal(sl, arr_3d[1])

    def test_between_last_coords_returns_last_slice(self, temporal_backend, arr_3d):
        # 2015 ∈ (2010, 2020) → ceiling → slice at 2020 (index 2)
        sl = temporal_backend.get("dist_roads", time=2015)
        np.testing.assert_array_equal(sl, arr_3d[2])

    def test_before_first_coord_clamps_to_first(self, temporal_backend, arr_3d):
        sl = temporal_backend.get("dist_roads", time=1990)
        np.testing.assert_array_equal(sl, arr_3d[0])

    def test_after_last_coord_clamps_to_last(self, temporal_backend, arr_3d):
        # searchsorted returns len(axis); the clamp prevents IndexError
        sl = temporal_backend.get("dist_roads", time=2030)
        np.testing.assert_array_equal(sl, arr_3d[2])

    def test_every_exact_coord_returns_its_own_slice(self, temporal_backend, arr_3d):
        for i, t in enumerate([2000, 2010, 2020]):
            np.testing.assert_array_equal(
                temporal_backend.get("dist_roads", time=t), arr_3d[i]
            )


# ── 3. string time coordinates ────────────────────────────────────────────────

class TestStringTimeCoords:
    """disscube passes raw xarray coords, which may be strings."""

    @pytest.fixture
    def str_backend(self, arr_3d):
        b = RasterBackend(shape=(3, 4))
        b.set("v", arr_3d[:2], time=["2000-01", "2010-01"])
        return b

    def test_round_trip(self, str_backend, arr_3d):
        assert str_backend.is_temporal("v")
        np.testing.assert_array_equal(
            str_backend.time_axis("v"), ["2000-01", "2010-01"]
        )
        np.testing.assert_array_equal(
            str_backend.get("v", time="2000-01"), arr_3d[0]
        )
        np.testing.assert_array_equal(
            str_backend.get("v", time="2010-01"), arr_3d[1]
        )

    def test_between_coords_lexicographic_ceiling(self, str_backend, arr_3d):
        # same ceiling rule, applied lexicographically on strings
        np.testing.assert_array_equal(
            str_backend.get("v", time="2005-06"), arr_3d[1]
        )

    def test_boundaries_clamp_without_raising(self, str_backend, arr_3d):
        np.testing.assert_array_equal(
            str_backend.get("v", time="1999-01"), arr_3d[0]
        )
        np.testing.assert_array_equal(
            str_backend.get("v", time="2020-01"), arr_3d[1]
        )


# ── 4. validation ─────────────────────────────────────────────────────────────

class TestValidation:

    def test_time_length_mismatch_raises(self, arr_3d):
        b = RasterBackend(shape=(3, 4))
        with pytest.raises(ValueError, match="time length"):
            b.set("v", arr_3d, time=[2000, 2010])  # 2 coords, 3 slices

    def test_2d_array_with_time_raises(self):
        b = RasterBackend(shape=(3, 4))
        with pytest.raises(ValueError, match="Expected 3D"):
            b.set("v", np.zeros((3, 4)), time=[2000])

    def test_failed_set_does_not_register_variable(self, arr_3d):
        b = RasterBackend(shape=(3, 4))
        with pytest.raises(ValueError):
            b.set("v", arr_3d, time=[2000])
        assert "v" not in b.band_names()

    def test_get_unknown_name_raises_keyerror(self):
        b = RasterBackend(shape=(3, 4))
        with pytest.raises(KeyError):
            b.get("missing")


# ── 5. static path unchanged ──────────────────────────────────────────────────

class TestStaticPath:

    def test_static_is_not_temporal(self, temporal_backend):
        assert temporal_backend.is_temporal("slope") is False

    def test_static_time_axis_is_none(self, temporal_backend):
        assert temporal_backend.time_axis("slope") is None

    def test_get_static_ignores_time(self, temporal_backend):
        """CA models call get(name, time=step) uniformly — static vars
        must silently ignore the time argument."""
        expected = temporal_backend.get("slope")
        got = temporal_backend.get("slope", time=5)
        assert got.shape == (3, 4)
        np.testing.assert_array_equal(got, expected)


# ── 6. re-set demotes to static ───────────────────────────────────────────────

class TestResetDemotion:

    def test_reset_with_2d_removes_time_axis(self, temporal_backend):
        temporal_backend.set("dist_roads", np.zeros((3, 4)))
        assert temporal_backend.is_temporal("dist_roads") is False
        assert temporal_backend.time_axis("dist_roads") is None
        assert temporal_backend.get("dist_roads", time=2010).shape == (3, 4)

    def test_reset_with_time_promotes_static(self, temporal_backend, arr_3d):
        temporal_backend.set("slope", arr_3d, time=[1, 2, 3])
        assert temporal_backend.is_temporal("slope") is True


# ── 7. partition helpers ──────────────────────────────────────────────────────

class TestPartitionHelpers:

    def test_partition_no_overlap_no_omission(self, temporal_backend):
        temporal = set(temporal_backend.temporal_band_names())
        static = set(temporal_backend.static_band_names())
        assert temporal == {"dist_roads"}
        assert static == {"slope"}
        assert temporal & static == set()
        assert temporal | static == set(temporal_backend.band_names())

    def test_rename_band_moves_time_axis(self, temporal_backend):
        temporal_backend.rename_band("dist_roads", "roads")
        assert temporal_backend.is_temporal("roads")
        assert not temporal_backend.is_temporal("dist_roads")
        np.testing.assert_array_equal(
            temporal_backend.time_axis("roads"), [2000, 2010, 2020]
        )


# ── 8. from_xarray temporal import ────────────────────────────────────────────

@requires_xarray
class TestFromXarrayTemporal:

    @pytest.fixture
    def mixed_dataset(self, arr_3d):
        coords = {"time": [2000, 2010, 2020],
                  "y": np.arange(3.0), "x": np.arange(4.0)}
        return xr.Dataset(
            {
                "dist_roads": xr.DataArray(
                    arr_3d, dims=("time", "y", "x"), coords=coords
                ),
                "slope": xr.DataArray(
                    np.arange(12, dtype=float).reshape(3, 4),
                    dims=("y", "x"),
                    coords={"y": coords["y"], "x": coords["x"]},
                ),
            }
        )

    def test_both_variables_imported(self, mixed_dataset):
        b = RasterBackend.from_xarray(mixed_dataset)
        assert set(b.band_names()) == {"dist_roads", "slope"}

    def test_temporal_classification_and_coords(self, mixed_dataset):
        b = RasterBackend.from_xarray(mixed_dataset)
        assert b.is_temporal("dist_roads")
        assert not b.is_temporal("slope")
        np.testing.assert_array_equal(
            b.time_axis("dist_roads"), [2000, 2010, 2020]
        )

    def test_shapes_and_values(self, mixed_dataset, arr_3d):
        b = RasterBackend.from_xarray(mixed_dataset)
        assert b.get("dist_roads").shape == (3, 3, 4)
        assert b.get("slope").shape == (3, 4)
        np.testing.assert_array_equal(b.get("dist_roads", time=2010), arr_3d[1])

    def test_dataarray_with_time_dim(self, arr_3d):
        da = xr.DataArray(
            arr_3d,
            dims=("time", "y", "x"),
            coords={"time": [2000, 2010, 2020],
                    "y": np.arange(3.0), "x": np.arange(4.0)},
            name="dist_roads",
        )
        b = RasterBackend.from_xarray(da)
        assert b.is_temporal("dist_roads")
        assert b.get("dist_roads").shape == (3, 3, 4)
        np.testing.assert_array_equal(
            b.time_axis("dist_roads"), [2000, 2010, 2020]
        )


# ── 9. to_xarray round-trip ───────────────────────────────────────────────────

@requires_xarray
class TestToXarrayRoundTrip:

    def test_temporal_var_emitted_as_3d(self, temporal_backend):
        ds = temporal_backend.to_xarray()
        assert ds["dist_roads"].dims == ("time", "y", "x")
        assert ds["slope"].dims == ("y", "x")
        np.testing.assert_array_equal(
            ds.coords["time"].values, [2000, 2010, 2020]
        )

    def test_round_trip_preserves_everything(self, temporal_backend, arr_3d):
        b2 = RasterBackend.from_xarray(temporal_backend.to_xarray())

        assert b2.shape == temporal_backend.shape
        assert set(b2.temporal_band_names()) == {"dist_roads"}
        assert set(b2.static_band_names()) == {"slope"}
        np.testing.assert_array_equal(
            b2.time_axis("dist_roads"), [2000, 2010, 2020]
        )
        np.testing.assert_array_equal(b2.get("dist_roads"), arr_3d)
        np.testing.assert_array_equal(
            b2.get("slope"), temporal_backend.get("slope")
        )
