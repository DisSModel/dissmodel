"""
tests/executor/test_utils_config.py
====================================
Tests for dissmodel.executor.utils — default_output_uri — and
dissmodel.executor.config — Settings.
"""
from __future__ import annotations

from dissmodel.executor.utils import default_output_uri
from dissmodel.executor.config import Settings, settings
from dissmodel.io import _storage


class TestDefaultOutputUri:

    def teardown_method(self):
        _storage.set_default_client(None)

    def test_s3_uri_when_minio_reachable(self):
        _storage.set_default_client(object())  # any non-None client
        uri = default_output_uri("exp-123", "tif")
        assert uri == "s3://dissmodel-outputs/experiments/exp-123/output.tif"

    def test_local_fallback_when_minio_unreachable(self, monkeypatch):
        _storage.set_default_client(None)

        def boom():
            raise RuntimeError("no MinIO")

        monkeypatch.setattr(
            "dissmodel.io._storage.get_default_client", boom
        )
        uri = default_output_uri("exp-123", "gpkg")
        assert uri == "./outputs/exp-123/output.gpkg"


class TestSettings:

    def test_default_output_base(self):
        assert Settings().default_output_base == "./outputs"

    def test_module_level_singleton_exists(self):
        assert isinstance(settings, Settings)

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_OUTPUT_BASE", "/data/runs")
        assert Settings().default_output_base == "/data/runs"
