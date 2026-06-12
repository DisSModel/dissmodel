"""
tests/io/test_vector_io.py
===========================
Tests for dissmodel.io.vector — GeoDataFrame load/save round-trips
(GeoPackage), plus s3:// upload via fake client.
"""
from __future__ import annotations

import pytest

gpd = pytest.importorskip("geopandas")

from shapely.geometry import Polygon  # noqa: E402

from dissmodel.io.vector import load_gdf, save_gdf  # noqa: E402
from dissmodel.io._utils import sha256_file  # noqa: E402


@pytest.fixture
def gdf():
    geoms = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
    ]
    return gpd.GeoDataFrame(
        {"uso": [1, 2], "alt": [0.5, 1.5]},
        geometry=geoms,
        crs="EPSG:31984",
    )


class FakeMinioClient:
    def __init__(self):
        self.store: dict[tuple[str, str], bytes] = {}

    def put_object(self, bucket_name, object_name, data, length, content_type):
        self.store[(bucket_name, object_name)] = data.read()


class TestVectorIO:

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_roundtrip_gpkg(self, gdf, tmp_path):
        path = tmp_path / "grid.gpkg"
        checksum = save_gdf(gdf, str(path))

        loaded, load_checksum = load_gdf(str(path))
        assert list(loaded["uso"]) == [1, 2]
        assert loaded.crs is not None
        assert checksum == load_checksum == sha256_file(str(path))

    def test_save_custom_layer(self, gdf, tmp_path):
        path = tmp_path / "layers.gpkg"
        save_gdf(gdf, str(path), layer="simulation")
        loaded = gpd.read_file(str(path), layer="simulation")
        assert len(loaded) == 2

    def test_save_to_s3(self, gdf):
        client = FakeMinioClient()
        checksum = save_gdf(gdf, "s3://bucket/out/grid.gpkg", minio_client=client)
        payload = client.store[("bucket", "out/grid.gpkg")]
        assert len(payload) > 0
        assert isinstance(checksum, str) and len(checksum) == 64

    def test_load_geojson(self, gdf, tmp_path):
        path = tmp_path / "grid.geojson"
        gdf.to_file(str(path), driver="GeoJSON")
        loaded, checksum = load_gdf(str(path))
        assert len(loaded) == 2
        assert checksum == sha256_file(str(path))
