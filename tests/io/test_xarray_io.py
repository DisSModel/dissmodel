"""
tests/io/test_xarray_io.py
===========================
Tests for dissmodel.io._xarray — NetCDF and Zarr round-trips through
RasterBackend.to_xarray() / from_xarray().
"""
from __future__ import annotations

import numpy as np
import pytest

xr = pytest.importorskip("xarray")

from dissmodel.geo.raster.backend import RasterBackend  # noqa: E402
from dissmodel.io._xarray import load_xarray, save_xarray, _file_checksum  # noqa: E402
from dissmodel.io._utils import sha256_file  # noqa: E402


@pytest.fixture
def backend():
    b = RasterBackend(shape=(3, 4))
    b.arrays["uso"] = np.arange(12, dtype=np.int32).reshape(3, 4)
    b.arrays["alt"] = np.linspace(0, 1, 12, dtype=np.float32).reshape(3, 4)
    return b


class TestNetCDF:

    @pytest.mark.filterwarnings("ignore::UserWarning")
    def test_roundtrip(self, backend, tmp_path):
        path = tmp_path / "snapshot.nc"
        checksum = save_xarray(backend, str(path))

        loaded, load_checksum = load_xarray(str(path))
        assert loaded.shape == backend.shape
        np.testing.assert_array_equal(loaded.arrays["uso"], backend.arrays["uso"])
        np.testing.assert_allclose(loaded.arrays["alt"], backend.arrays["alt"])
        assert checksum == load_checksum == sha256_file(str(path))

    def test_save_with_step_attaches_time(self, backend, tmp_path):
        path = tmp_path / "step42.nc"
        save_xarray(backend, str(path), step=42)
        ds = xr.open_dataset(str(path))
        assert "time" in ds.coords
        assert int(ds["time"].values) == 42
        ds.close()

    def test_save_accepts_raw_dataset(self, backend, tmp_path):
        ds = backend.to_xarray()
        path = tmp_path / "raw.nc"
        checksum = save_xarray(ds, str(path))
        assert path.exists()
        assert checksum == sha256_file(str(path))

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_xarray(str(tmp_path / "missing.nc"))


class TestZarr:

    def test_roundtrip(self, backend, tmp_path):
        pytest.importorskip("zarr")
        path = tmp_path / "cube.zarr"
        checksum = save_xarray(backend, str(path))
        assert checksum == ""  # remote/zarr checksum deferred (documented)

        loaded, load_checksum = load_xarray(str(path))
        assert load_checksum == ""
        np.testing.assert_array_equal(loaded.arrays["uso"], backend.arrays["uso"])


class TestFileChecksum:

    def test_existing_file(self, tmp_path):
        path = tmp_path / "f.bin"
        path.write_bytes(b"abc")
        assert _file_checksum(str(path)) == sha256_file(str(path))

    def test_missing_file_returns_empty(self, tmp_path):
        assert _file_checksum(str(tmp_path / "missing")) == ""
