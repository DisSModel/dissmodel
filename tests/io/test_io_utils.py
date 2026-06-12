"""
tests/io/test_io_utils.py
==========================
Tests for dissmodel.io._utils — format detection, checksums, and
generic URI read/write helpers.

s3:// paths are exercised with an in-memory fake MinIO client so no
network or server is required.
"""
from __future__ import annotations

import hashlib
import io

import pytest

from dissmodel.io._utils import (
    detect_format,
    sha256_bytes,
    sha256_file,
    resolve_uri,
    read_bytes,
    read_text,
    write_bytes,
    write_text,
)
from dissmodel.io import _storage


# ── fakes ─────────────────────────────────────────────────────────────────────

class _FakeObject:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeMinioClient:
    """Minimal in-memory stand-in for the MinIO client."""

    def __init__(self):
        self.store: dict[tuple[str, str], bytes] = {}

    def get_object(self, bucket: str, key: str) -> _FakeObject:
        return _FakeObject(self.store[(bucket, key)])

    def put_object(self, bucket_name, object_name, data, length, content_type):
        self.store[(bucket_name, object_name)] = data.read()


@pytest.fixture
def fake_client():
    client = FakeMinioClient()
    _storage.set_default_client(client)
    yield client
    _storage.set_default_client(None)


# ══════════════════════════════════════════════════════════════════════════════
# detect_format
# ══════════════════════════════════════════════════════════════════════════════

class TestDetectFormat:

    @pytest.mark.parametrize("uri", [
        "data/grid.shp",
        "data/grid.gpkg",
        "data/grid.geojson",
        "data/grid.json",
        "data/grid.zip",
        "s3://bucket/key.GPKG",          # case-insensitive
    ])
    def test_vector_extensions(self, uri):
        assert detect_format(uri) == "vector"

    @pytest.mark.parametrize("uri", [
        "data/scene.tif",
        "data/scene.tiff",
        "https://example.org/scene.TIF",
    ])
    def test_raster_extensions(self, uri):
        assert detect_format(uri) == "raster"

    @pytest.mark.parametrize("uri", [
        "data/cube.zarr",
        "data/cube.nc",
        "data/cube.nc4",
    ])
    def test_xarray_extensions(self, uri):
        assert detect_format(uri) == "xarray"

    def test_query_string_is_stripped(self):
        assert detect_format("https://host/scene.tif?token=abc") == "raster"

    def test_unknown_extension_raises(self):
        with pytest.raises(ValueError, match="Cannot detect format"):
            detect_format("data/file.xyz")

    def test_no_extension_raises(self):
        with pytest.raises(ValueError):
            detect_format("data/file")


# ══════════════════════════════════════════════════════════════════════════════
# checksums
# ══════════════════════════════════════════════════════════════════════════════

class TestChecksums:

    def test_sha256_bytes_matches_hashlib(self):
        payload = b"dissmodel"
        assert sha256_bytes(payload) == hashlib.sha256(payload).hexdigest()

    def test_sha256_bytes_empty(self):
        assert sha256_bytes(b"") == hashlib.sha256(b"").hexdigest()

    def test_sha256_file_matches_bytes_digest(self, tmp_path):
        payload = b"x" * 200_000  # larger than one 65536-byte chunk
        path = tmp_path / "blob.bin"
        path.write_bytes(payload)
        assert sha256_file(str(path)) == sha256_bytes(payload)


# ══════════════════════════════════════════════════════════════════════════════
# resolve_uri
# ══════════════════════════════════════════════════════════════════════════════

class TestResolveUri:

    def test_local_path(self, tmp_path):
        path = tmp_path / "data.txt"
        path.write_bytes(b"hello")
        content, checksum = resolve_uri(str(path))
        assert content == b"hello"
        assert checksum == sha256_bytes(b"hello")

    def test_local_path_missing_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_uri(str(tmp_path / "missing.txt"))

    def test_s3_with_explicit_client(self):
        client = FakeMinioClient()
        client.store[("bucket", "dir/data.bin")] = b"payload"
        content, checksum = resolve_uri("s3://bucket/dir/data.bin", client)
        assert content == b"payload"
        assert checksum == sha256_bytes(b"payload")

    def test_s3_falls_back_to_default_client(self, fake_client):
        fake_client.store[("bucket", "key")] = b"default"
        content, _ = resolve_uri("s3://bucket/key")
        assert content == b"default"

    def test_http_uses_urllib(self, monkeypatch):
        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b"web-content"

        import urllib.request
        monkeypatch.setattr(
            urllib.request, "urlopen", lambda uri: _FakeResponse()
        )
        content, checksum = resolve_uri("https://example.org/data.bin")
        assert content == b"web-content"
        assert checksum == sha256_bytes(b"web-content")


# ══════════════════════════════════════════════════════════════════════════════
# read_bytes / read_text
# ══════════════════════════════════════════════════════════════════════════════

class TestRead:

    def test_read_bytes_local(self, tmp_path):
        path = tmp_path / "data.bin"
        path.write_bytes(b"\x00\x01")
        assert read_bytes(str(path)) == b"\x00\x01"

    def test_read_text_local(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("key = 'value'", encoding="utf-8")
        assert read_text(str(path)) == "key = 'value'"

    def test_read_bytes_s3(self, fake_client):
        fake_client.store[("bucket", "data.bin")] = b"remote"
        assert read_bytes("s3://bucket/data.bin") == b"remote"


# ══════════════════════════════════════════════════════════════════════════════
# write_bytes / write_text
# ══════════════════════════════════════════════════════════════════════════════

class TestWrite:

    def test_write_bytes_local(self, tmp_path):
        target = tmp_path / "out" / "data.bin"   # parent does not exist yet
        checksum = write_bytes(b"payload", str(target))
        assert target.read_bytes() == b"payload"
        assert checksum == sha256_bytes(b"payload")

    def test_write_bytes_accepts_bytesio(self, tmp_path):
        buf = io.BytesIO(b"stream-data")
        target = tmp_path / "data.bin"
        checksum = write_bytes(buf, str(target))
        assert target.read_bytes() == b"stream-data"
        assert checksum == sha256_bytes(b"stream-data")

    def test_write_bytes_rejects_text_stream(self, tmp_path):
        with pytest.raises(TypeError, match="bytes or a binary stream"):
            write_bytes(io.StringIO("text"), str(tmp_path / "x.bin"))

    def test_write_bytes_rejects_str(self, tmp_path):
        with pytest.raises(TypeError):
            write_bytes("not-bytes", str(tmp_path / "x.bin"))

    def test_write_text_local(self, tmp_path):
        target = tmp_path / "report.md"
        checksum = write_text("# Report", str(target))
        assert target.read_text(encoding="utf-8") == "# Report"
        assert checksum == sha256_bytes(b"# Report")

    def test_write_bytes_s3(self, fake_client):
        checksum = write_bytes(b"upload", "s3://bucket/dir/file.bin")
        assert fake_client.store[("bucket", "dir/file.bin")] == b"upload"
        assert checksum == sha256_bytes(b"upload")

    def test_write_text_s3(self, fake_client):
        write_text("csv,data", "s3://bucket/results.csv", content_type="text/csv")
        assert fake_client.store[("bucket", "results.csv")] == b"csv,data"
