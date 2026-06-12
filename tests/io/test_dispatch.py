"""
tests/io/test_dispatch.py
==========================
Tests for dissmodel.io._dispatch — format routing of load_dataset and
save_dataset — and for dissmodel.io._storage — default MinIO client.

Routing is verified with monkeypatched loaders/savers so each test
asserts only the dispatch decision, not the underlying I/O.
"""
from __future__ import annotations

import sys

import pytest

from dissmodel.io import load_dataset, save_dataset
from dissmodel.io import _storage


# ══════════════════════════════════════════════════════════════════════════════
# load_dataset routing
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadDispatch:

    def test_routes_vector(self, monkeypatch):
        import dissmodel.io.vector as vector_mod
        monkeypatch.setattr(
            vector_mod, "load_gdf",
            lambda uri, minio_client=None, **kw: ("GDF", "sum"),
        )
        assert load_dataset("data/grid.gpkg") == ("GDF", "sum")

    def test_routes_raster(self, monkeypatch):
        import dissmodel.io.raster as raster_mod
        monkeypatch.setattr(
            raster_mod, "load_geotiff",
            lambda uri, minio_client=None, **kw: (("BACKEND", {}), "sum"),
        )
        assert load_dataset("data/scene.tif") == (("BACKEND", {}), "sum")

    def test_routes_xarray(self, monkeypatch):
        import dissmodel.io._xarray as xr_mod
        monkeypatch.setattr(
            xr_mod, "load_xarray",
            lambda uri, minio_client=None, **kw: ("DS", "sum"),
        )
        assert load_dataset("data/cube.nc") == ("DS", "sum")

    def test_explicit_fmt_overrides_extension(self, monkeypatch):
        import dissmodel.io.raster as raster_mod
        monkeypatch.setattr(
            raster_mod, "load_geotiff",
            lambda uri, minio_client=None, **kw: ("RASTER", "sum"),
        )
        # .dat is not a recognized extension — fmt= must win
        assert load_dataset("data/scene.dat", fmt="raster") == ("RASTER", "sum")

    def test_unsupported_fmt_raises(self):
        with pytest.raises(ValueError, match="Unsupported format"):
            load_dataset("data/scene.tif", fmt="hologram")

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError):
            load_dataset("data/file.xyz")


# ══════════════════════════════════════════════════════════════════════════════
# save_dataset routing
# ══════════════════════════════════════════════════════════════════════════════

class TestSaveDispatch:

    def test_routes_vector(self, monkeypatch):
        import dissmodel.io.vector as vector_mod
        monkeypatch.setattr(
            vector_mod, "save_gdf",
            lambda data, uri, minio_client=None, **kw: "checksum-v",
        )
        assert save_dataset("GDF", "out/grid.gpkg") == "checksum-v"

    def test_routes_raster(self, monkeypatch):
        import dissmodel.io.raster as raster_mod
        monkeypatch.setattr(
            raster_mod, "save_geotiff",
            lambda data, uri, minio_client=None, **kw: "checksum-r",
        )
        assert save_dataset(("BACKEND", {}), "out/scene.tif") == "checksum-r"

    def test_routes_xarray(self, monkeypatch):
        import dissmodel.io._xarray as xr_mod
        monkeypatch.setattr(
            xr_mod, "save_xarray",
            lambda data, uri, minio_client=None, **kw: "checksum-x",
        )
        assert save_dataset("DS", "out/cube.zarr") == "checksum-x"

    def test_unsupported_fmt_raises(self):
        with pytest.raises(ValueError, match="Unsupported format"):
            save_dataset("DATA", "out/scene.tif", fmt="hologram")


# ══════════════════════════════════════════════════════════════════════════════
# _storage — default MinIO client
# ══════════════════════════════════════════════════════════════════════════════

class TestStorage:

    def setup_method(self):
        _storage.set_default_client(None)

    def teardown_method(self):
        _storage.set_default_client(None)

    def test_set_default_client_overrides(self):
        sentinel = object()
        _storage.set_default_client(sentinel)
        assert _storage.get_default_client() is sentinel

    def test_get_default_client_builds_from_env(self, monkeypatch):
        created = {}

        class FakeMinio:
            def __init__(self, endpoint, access_key, secret_key, secure):
                created.update(
                    endpoint=endpoint,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=secure,
                )

        fake_module = type(sys)("minio")
        fake_module.Minio = FakeMinio
        monkeypatch.setitem(sys.modules, "minio", fake_module)
        monkeypatch.setenv("MINIO_ENDPOINT", "host:9000")
        monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
        monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
        monkeypatch.setenv("MINIO_SECURE", "1")

        client = _storage.get_default_client()
        assert isinstance(client, FakeMinio)
        assert created == {
            "endpoint": "host:9000",
            "access_key": "ak",
            "secret_key": "sk",
            "secure": True,
        }

    def test_get_default_client_is_cached(self, monkeypatch):
        class FakeMinio:
            def __init__(self, *a, **kw):
                pass

        fake_module = type(sys)("minio")
        fake_module.Minio = FakeMinio
        monkeypatch.setitem(sys.modules, "minio", fake_module)

        first = _storage.get_default_client()
        second = _storage.get_default_client()
        assert first is second

    def test_missing_minio_package_raises_importerror(self, monkeypatch):
        # sys.modules[name] = None makes ``import name`` raise ImportError
        monkeypatch.setitem(sys.modules, "minio", None)
        with pytest.raises(ImportError, match="minio"):
            _storage.get_default_client()
