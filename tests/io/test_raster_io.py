"""
tests/io/test_raster_io.py
===========================
Tests for dissmodel.io.raster — GeoTIFF load/save round-trips.

Covers: local round-trip, band_spec selection, zip archives, nodata
band skipping, s3:// upload via fake client, and metadata recovery
(CRS + transform).
"""
from __future__ import annotations

import zipfile

import numpy as np
import pytest

pytest.importorskip("rasterio")

import rasterio  # noqa: E402
import rasterio.transform  # noqa: E402

from dissmodel.geo.raster.backend import RasterBackend  # noqa: E402
from dissmodel.io.raster import load_geotiff, save_geotiff  # noqa: E402
from dissmodel.io._utils import sha256_file  # noqa: E402


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def backend():
    b = RasterBackend(shape=(4, 5))
    b.arrays["uso"] = np.arange(20, dtype=np.int32).reshape(4, 5)
    b.arrays["alt"] = np.linspace(0, 1, 20, dtype=np.float32).reshape(4, 5)
    return b


@pytest.fixture
def saved_tif(backend, tmp_path):
    """A GeoTIFF written by save_geotiff, with known CRS and transform."""
    path = tmp_path / "scene.tif"
    transform = rasterio.transform.from_bounds(0, 0, 500, 400, 5, 4)
    band_spec = [("uso", "int32", -1), ("alt", "float32", -9999.0)]
    checksum = save_geotiff(
        (backend, {}),
        str(path),
        band_spec=band_spec,
        crs="EPSG:31984",
        transform=transform,
    )
    return path, band_spec, checksum


class FakeMinioClient:
    def __init__(self):
        self.store: dict[tuple[str, str], bytes] = {}

    def put_object(self, bucket_name, object_name, data, length, content_type):
        self.store[(bucket_name, object_name)] = data.read()

    def get_object(self, bucket, key):
        payload = self.store[(bucket, key)]

        class _Obj:
            def read(self_inner):
                return payload

        return _Obj()


# ══════════════════════════════════════════════════════════════════════════════
# save_geotiff
# ══════════════════════════════════════════════════════════════════════════════

class TestSaveGeotiff:

    def test_returns_file_checksum(self, saved_tif):
        path, _, checksum = saved_tif
        assert checksum == sha256_file(str(path))

    def test_creates_parent_directories(self, backend, tmp_path):
        target = tmp_path / "nested" / "dir" / "scene.tif"
        save_geotiff((backend, {}), str(target))
        assert target.exists()

    def test_without_band_spec_writes_all_arrays(self, backend, tmp_path):
        path = tmp_path / "all.tif"
        save_geotiff((backend, {}), str(path))
        with rasterio.open(str(path)) as ds:
            assert ds.count == 2

    def test_meta_crs_and_transform_are_used(self, backend, tmp_path):
        path = tmp_path / "meta.tif"
        transform = rasterio.transform.from_bounds(10, 20, 510, 420, 5, 4)
        meta = {"crs": "EPSG:4326", "transform": transform}
        save_geotiff((backend, meta), str(path))
        with rasterio.open(str(path)) as ds:
            assert ds.crs.to_string() == "EPSG:4326"
            assert ds.transform == transform

    def test_explicit_crs_overrides_meta(self, backend, tmp_path):
        path = tmp_path / "override.tif"
        save_geotiff((backend, {"crs": "EPSG:4326"}), str(path), crs="EPSG:31984")
        with rasterio.open(str(path)) as ds:
            assert "31984" in ds.crs.to_string()

    def test_band_spec_fills_missing_band_with_nodata(self, backend, tmp_path):
        path = tmp_path / "fill.tif"
        spec = [("uso", "int32", -1), ("inexistente", "int32", -1)]
        save_geotiff((backend, {}), str(path), band_spec=spec)
        with rasterio.open(str(path)) as ds:
            assert ds.count == 2
            assert np.all(ds.read(2) == -1)

    def test_s3_upload(self, backend):
        client = FakeMinioClient()
        checksum = save_geotiff(
            (backend, {}), "s3://bucket/exp/scene.tif", minio_client=client
        )
        payload = client.store[("bucket", "exp/scene.tif")]
        assert len(payload) > 0
        assert isinstance(checksum, str) and len(checksum) == 64

    def test_mixed_dtype_bands_are_not_truncated(self, backend, tmp_path):
        """Regression: int32 + float32 bands must promote to a common
        dtype instead of truncating floats to the first band's dtype."""
        path = tmp_path / "mixed.tif"
        spec = [("uso", "int32", -1), ("alt", "float32", -9999.0)]
        save_geotiff((backend, {}), str(path), band_spec=spec)

        with rasterio.open(str(path)) as ds:
            alt = ds.read(2)
        np.testing.assert_allclose(alt, backend.arrays["alt"], rtol=1e-6)


# ══════════════════════════════════════════════════════════════════════════════
# load_geotiff
# ══════════════════════════════════════════════════════════════════════════════

class TestLoadGeotiff:

    def test_roundtrip_with_band_spec(self, backend, saved_tif):
        path, band_spec, _ = saved_tif
        (loaded, meta), checksum = load_geotiff(str(path), band_spec=band_spec)

        assert loaded.shape == backend.shape
        np.testing.assert_array_equal(loaded.arrays["uso"], backend.arrays["uso"])
        np.testing.assert_allclose(loaded.arrays["alt"], backend.arrays["alt"])
        assert checksum == sha256_file(str(path))

    def test_roundtrip_recovers_crs_and_transform(self, saved_tif):
        path, band_spec, _ = saved_tif
        (_, meta), _ = load_geotiff(str(path), band_spec=band_spec)
        assert "31984" in meta["crs"].to_string()
        assert meta["transform"] is not None

    def test_without_band_spec_recovers_tag_names(self, saved_tif):
        path, _, _ = saved_tif
        (loaded, _), _ = load_geotiff(str(path))
        # save_geotiff writes a 'name' tag per band — loader recovers it
        assert set(loaded.arrays) == {"uso", "alt"}

    def test_band_spec_skips_all_nodata_band(self, tmp_path):
        b = RasterBackend(shape=(2, 2))
        b.arrays["uso"]   = np.ones((2, 2), dtype=np.int32)
        b.arrays["vazio"] = np.full((2, 2), -1, dtype=np.int32)
        path = tmp_path / "skip.tif"
        spec = [("uso", "int32", -1), ("vazio", "int32", -1)]
        save_geotiff((b, {}), str(path), band_spec=spec)

        (loaded, _), _ = load_geotiff(str(path), band_spec=spec)
        assert "uso" in loaded.arrays
        assert "vazio" not in loaded.arrays  # uninitialised band skipped

    def test_band_spec_longer_than_band_count_is_truncated(self, saved_tif):
        path, _, _ = saved_tif
        spec = [
            ("uso", "int32", -1),
            ("alt", "float32", -9999.0),
            ("extra", "int32", -1),      # no third band in the file
        ]
        (loaded, _), _ = load_geotiff(str(path), band_spec=spec)
        assert "extra" not in loaded.arrays

    def test_load_from_zip_archive(self, saved_tif, tmp_path):
        path, band_spec, _ = saved_tif
        zip_path = tmp_path / "scene.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(path, arcname="scene.tif")

        (loaded, _), checksum = load_geotiff(str(zip_path), band_spec=band_spec)
        assert loaded.shape == (4, 5)
        assert checksum == sha256_file(str(zip_path))

    def test_load_from_s3(self, saved_tif):
        path, band_spec, _ = saved_tif
        client = FakeMinioClient()
        client.store[("bucket", "scene.tif")] = path.read_bytes()

        (loaded, _), _ = load_geotiff(
            "s3://bucket/scene.tif", minio_client=client, band_spec=band_spec
        )
        assert loaded.shape == (4, 5)
