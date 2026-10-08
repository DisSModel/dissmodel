"""
tests/raster/test_raster_map.py
=================================
Tests for RasterMap — raster visualization component.

RasterMap renders at each step.
Tests cover: instantiation, mode detection (categorical/continuous),
headless rendering (no display required), and environment integration.
"""
from __future__ import annotations

import os
import pytest
import numpy as np

from dissmodel.core import Environment
from dissmodel.geo.raster.backend import RasterBackend
from dissmodel.geo import raster_grid
from dissmodel.visualization.raster_map import RasterMap


@pytest.fixture(autouse=True)
def _run_in_tmp_path(tmp_path, monkeypatch):
    """Headless Chart/RasterMap write PNG frames to the working directory;
    run every test in a temporary one so the repository stays clean."""
    monkeypatch.chdir(tmp_path)


# ── force headless for all tests ──────────────────────────────────────────────

@pytest.fixture(autouse=True)
def headless(monkeypatch):
    monkeypatch.setenv("MPLBACKEND", "Agg")
    monkeypatch.delenv("RASTER_MAP_INTERACTIVE", raising=False)


@pytest.fixture
def backend():
    uso = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=np.int32)
    alt = np.linspace(0, 1, 9, dtype=np.float32).reshape(3, 3)
    return raster_grid(rows=3, cols=3, attrs={"uso": uso, "alt": alt})


# ══════════════════════════════════════════════════════════════════════════════
# Instantiation
# ══════════════════════════════════════════════════════════════════════════════

class TestInstantiation:

    def test_categorical_mode(self, backend):
        env = Environment(start_time=1, end_time=1)
        color_map = {i: f"#{i:02x}{i:02x}{i:02x}" for i in range(1, 10)}
        m = RasterMap(backend=backend, band="uso", save_frames=True, color_map=color_map)
        assert m is not None

    def test_continuous_mode(self, backend):
        env = Environment(start_time=1, end_time=1)
        m = RasterMap(backend=backend, band="alt", save_frames=True, cmap="terrain",
                      vmin=0.0, vmax=1.0)
        assert m is not None

    def test_default_band(self, backend):
        env = Environment(start_time=1, end_time=1)
        m = RasterMap(backend=backend, save_frames=True, band="uso")
        assert m.band == "uso"


# ══════════════════════════════════════════════════════════════════════════════
# Rendering — headless (no display)
# ══════════════════════════════════════════════════════════════════════════════

class TestHeadlessRender:

    def test_runs_without_display(self, backend):
        """RasterMap must not raise when no display is available."""
        env = Environment(start_time=1, end_time=3)
        color_map = {i: "blue" for i in range(1, 10)}
        RasterMap(backend=backend, band="uso", save_frames=True,color_map=color_map)
        env.run()   # must complete without error

    def test_continuous_runs_without_display(self, backend):
        env = Environment(start_time=1, end_time=3)
        RasterMap(backend=backend, band="alt",save_frames=True, cmap="viridis",
                  vmin=0.0, vmax=1.0)
        env.run()


# ══════════════════════════════════════════════════════════════════════════════
# Environment integration
# ══════════════════════════════════════════════════════════════════════════════

class TestEnvironmentIntegration:

    def test_map_and_model_share_env(self, backend):
        """RasterMap and a model run in the same environment without conflict."""
        from dissmodel.geo.raster.raster_model import RasterModel

        class IncModel(RasterModel):
            def setup(self, backend): super().setup(backend)
            def execute(self): self.backend.arrays["uso"] += 1

        env = Environment(start_time=1, end_time=3)
        IncModel(backend=backend)
        RasterMap(backend=backend,save_frames=True, band="uso")
        env.run()

        # model ran 3 steps — original values 1..9, now 4..12
        assert backend.get("uso").min() == 4

    def test_map_does_not_mutate_backend(self, backend):
        """RasterMap must only read arrays, never write to them."""
        original = backend.get("uso").copy()
        env = Environment(start_time=1, end_time=3)
        RasterMap(backend=backend,save_frames=True, band="uso")
        env.run()
        np.testing.assert_array_equal(backend.get("uso"), original)
