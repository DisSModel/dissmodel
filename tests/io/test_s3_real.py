"""
tests/io/test_s3_real.py
=========================
Integration tests against a REAL S3-protocol server — moto's
``ThreadedMotoServer``, running in-process on an ephemeral port. No
Docker and no network access are required; the server is pure Python.

Every other s3:// test in this suite (test_io_utils.py, test_raster_io.py)
uses ``FakeMinioClient``, an in-memory stand-in that only implements
``get_object``/``put_object``. That fake has therefore never exercised
``ModelExecutor._resolve_uri``, which calls ``minio.fget_object`` — the
exact path the CLI takes for ``--input s3://...`` / ``--output s3://...``.
These tests run the real ``minio`` client against a real S3-compatible
HTTP server instead, covering that gap and giving an end-to-end sanity
check of the whole chain (HTTP, auth headers, request signing) that a
fake client can't.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("minio")
pytest.importorskip("moto")

import rasterio
import rasterio.transform

from dissmodel.executor.model_executor import ModelExecutor
from dissmodel.io import _storage
from dissmodel.io.raster import load_geotiff, save_geotiff

BUCKET = "dissmodel-test"


# ── server + client fixtures ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def s3_server():
    """A real, in-process S3-protocol server on an ephemeral port."""
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"{host}:{port}"
    server.stop()


@pytest.fixture
def s3_client(s3_server):
    """A real ``minio.Minio`` client, wired to the ephemeral test server
    and registered as dissmodel's default client for the duration of the
    test."""
    from minio import Minio

    client = Minio(
        s3_server,
        access_key="testing",
        secret_key="testing",
        secure=False,
    )
    client.make_bucket(BUCKET)
    _storage.set_default_client(client)
    yield client
    _storage.set_default_client(None)


@pytest.fixture
def raster_backend():
    from dissmodel.geo.raster.backend import RasterBackend

    b = RasterBackend(shape=(5, 5), crs="EPSG:4326")
    b.arrays["uso"] = np.arange(25, dtype=np.int32).reshape(5, 5)
    return b


@pytest.fixture
def uploaded_tif(s3_client, raster_backend, tmp_path):
    """A GeoTIFF written with rasterio and uploaded to the test bucket
    via the real minio client — independent of dissmodel's own
    save_geotiff, so load-side tests don't depend on save-side code."""
    local_path = tmp_path / "scene.tif"
    transform = rasterio.transform.from_origin(-45.0, -2.0, 0.001, 0.001)
    with rasterio.open(
        local_path, "w", driver="GTiff",
        height=5, width=5, count=1, dtype="int32",
        crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(raster_backend.arrays["uso"], 1)

    s3_client.fput_object(BUCKET, "rasters/scene.tif", str(local_path))
    return local_path


# ── ModelExecutor._resolve_uri — the CLI's --input s3://... path ──────────

class _DummyExecutor(ModelExecutor):
    """Minimal concrete ModelExecutor — only _resolve_uri is under test."""
    name = "dummy-s3-test"

    def validate(self, record):
        pass

    def load(self, record):
        pass

    def run(self, data, record):
        pass

    def save(self, result, record):
        pass


class TestResolveUriAgainstRealServer:
    """``_resolve_uri`` is what the CLI calls for ``--input s3://...``.
    It uses ``minio.fget_object``, which FakeMinioClient never implements
    — so until now, this path had zero test coverage."""

    def test_downloads_s3_object_to_local_tmp(self, uploaded_tif, s3_client):
        executor = _DummyExecutor()
        local_path = executor._resolve_uri("s3://dissmodel-test/rasters/scene.tif")

        assert local_path == "/tmp/scene.tif"
        with rasterio.open(local_path) as f, rasterio.open(uploaded_tif) as g:
            assert np.array_equal(f.read(), g.read())

    def test_local_path_passes_through_unchanged(self):
        executor = _DummyExecutor()
        assert executor._resolve_uri("/local/data.tif") == "/local/data.tif"


# ── load_geotiff / save_geotiff round-trip via the real server ────────────

class TestRasterRoundTripAgainstRealServer:

    def test_load_matches_upload(self, uploaded_tif, s3_client, raster_backend):
        (backend, _meta), _checksum = load_geotiff("s3://dissmodel-test/rasters/scene.tif")
        loaded = backend.arrays[backend.band_names()[0]]
        assert np.array_equal(loaded, raster_backend.arrays["uso"])

    def test_save_then_reload_preserves_data(self, s3_client, raster_backend):
        checksum_saved = save_geotiff(
            (raster_backend, {}), "s3://dissmodel-test/rasters/roundtrip.tif"
        )

        (reloaded, _meta), checksum_loaded = load_geotiff(
            "s3://dissmodel-test/rasters/roundtrip.tif"
        )

        assert checksum_saved == checksum_loaded
        assert np.array_equal(
            reloaded.arrays[reloaded.band_names()[0]], raster_backend.arrays["uso"]
        )

        # confirm it actually landed in the bucket, not just round-tripped
        # through some local cache
        objects = {o.object_name for o in s3_client.list_objects(BUCKET, recursive=True)}
        assert "rasters/roundtrip.tif" in objects
