"""
tests/test_viz_fallback.py
===========================
ipywidgets is an optional dependency (pip install dissmodel[viz]).

These tests simulate a notebook environment where ipywidgets is absent
(sys.modules[name] = None makes ``import name`` raise ImportError) and
assert that Chart/Map/RasterMap setup falls back to the anchored-output-less
path (``_out is None``) instead of crashing.
"""
from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")  # headless backend for CI

import numpy as np
import pytest

from dissmodel.core import Environment
from dissmodel.geo import vector_grid
from dissmodel.geo.raster.backend import RasterBackend
from dissmodel.visualization.chart import Chart
from dissmodel.visualization.map import Map
from dissmodel.visualization.raster_map import RasterMap


@pytest.fixture
def no_ipywidgets(monkeypatch):
    """Make ``import ipywidgets`` raise ImportError inside the module code."""
    monkeypatch.setitem(sys.modules, "ipywidgets", None)


@pytest.fixture
def fake_notebook(monkeypatch):
    """Force the notebook code path in each visualization module."""
    monkeypatch.setattr(
        "dissmodel.visualization.chart.is_notebook", lambda: True
    )
    monkeypatch.setattr(
        "dissmodel.visualization.map.is_notebook", lambda: True
    )
    monkeypatch.setattr(
        "dissmodel.visualization.raster_map.is_notebook", lambda: True
    )


class TestWidgetFallback:

    def test_chart_setup_without_ipywidgets(self, fake_notebook, no_ipywidgets):
        Environment(start_time=0, end_time=1)
        chart = Chart()
        assert chart._out is None  # fell back, no crash

    def test_map_setup_without_ipywidgets(self, fake_notebook, no_ipywidgets):
        Environment(start_time=0, end_time=1)
        gdf = vector_grid(dimension=(2, 2), resolution=1.0)
        m = Map(gdf=gdf, plot_params={})
        assert m._out is None

    def test_raster_map_setup_without_ipywidgets(
        self, fake_notebook, no_ipywidgets
    ):
        Environment(start_time=0, end_time=1)
        backend = RasterBackend(shape=(2, 2))
        backend.set("state", np.zeros((2, 2), dtype=np.int8))
        rm = RasterMap(backend=backend, pause=False)
        assert rm._out is None

    def test_chart_setup_with_ipywidgets_outside_notebook(self):
        """Headless path (the default in CI) must not touch ipywidgets."""
        Environment(start_time=0, end_time=1)
        chart = Chart()
        assert chart._out is None
