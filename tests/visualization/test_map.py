"""
tests/visualization/test_map.py
================================
Tests for dissmodel.visualization.map — the Map (choropleth) component —
and dissmodel.visualization._utils — environment/backend detection.

All paths run headlessly (Agg backend).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from dissmodel.core import Environment
from dissmodel.geo import vector_grid
from dissmodel.visualization.map import Map
from dissmodel.visualization import _utils


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.fixture
def gdf():
    grid = vector_grid(dimension=(3, 3), resolution=1.0)
    grid["state"] = range(len(grid))
    return grid


# ══════════════════════════════════════════════════════════════════════════════
# Map — setup
# ══════════════════════════════════════════════════════════════════════════════

class TestMapSetup:

    def test_defaults(self, gdf):
        Environment(start_time=0, end_time=1)
        m = Map(gdf=gdf, plot_params={"column": "state"})
        assert m.figsize == (10, 6)
        assert m.pause is True
        assert m.fig is not None and m.ax is not None

    def test_custom_figsize(self, gdf):
        Environment(start_time=0, end_time=1)
        m = Map(gdf=gdf, plot_params={}, figsize=(4, 3))
        assert tuple(m.fig.get_size_inches()) == (4.0, 3.0)


# ══════════════════════════════════════════════════════════════════════════════
# Map — rendering and execution targets
# ══════════════════════════════════════════════════════════════════════════════

class TestMapExecute:

    def test_render_sets_step_title(self, gdf):
        Environment(start_time=0, end_time=1)
        m = Map(gdf=gdf, plot_params={"column": "state"}, pause=False)
        fig = m._render(step=3)
        assert "Step 3" in fig.axes[0].get_title()

    def test_headless_save_frames_writes_png(self, gdf, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env = Environment(start_time=0, end_time=2)
        Map(gdf=gdf, plot_params={"column": "state"}, save_frames=True, pause=False)
        env.run()

        frames = sorted((tmp_path / "map_frames").glob("state_step_*.png"))
        assert len(frames) >= 1

    def test_save_frame_uses_default_name_without_column(
        self, gdf, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        env = Environment(start_time=0, end_time=1)
        Map(gdf=gdf, plot_params={}, save_frames=True, pause=False)
        env.run()
        frames = list((tmp_path / "map_frames").glob("map_step_*.png"))
        assert len(frames) >= 1

    def test_streamlit_plot_area_receives_figure(self, gdf):
        class FakePlotArea:
            def __init__(self):
                self.figures = []

            def pyplot(self, fig):
                self.figures.append(fig)

        area = FakePlotArea()
        env = Environment(start_time=0, end_time=2)
        Map(gdf=gdf, plot_params={"column": "state"}, plot_area=area, pause=False)
        env.run()
        assert len(area.figures) >= 1

    def test_notebook_path_without_widget(self, gdf, monkeypatch):
        import sys
        monkeypatch.setattr(
            "dissmodel.visualization.map.is_notebook", lambda: True
        )
        monkeypatch.setitem(sys.modules, "ipywidgets", None)
        env = Environment(start_time=0, end_time=1)
        m = Map(gdf=gdf, plot_params={"column": "state"}, pause=False)
        assert m._out is None
        env.run()  # exercises notebook fallback branch without raising

    def test_notebook_path_with_anchored_widget(self, gdf, monkeypatch):
        monkeypatch.setattr(
            "dissmodel.visualization.map.is_notebook", lambda: True
        )
        env = Environment(start_time=0, end_time=1)
        m = Map(gdf=gdf, plot_params={"column": "state"}, pause=False)
        if m._out is None:
            pytest.skip("ipywidgets not installed — fallback covered elsewhere")
        env.run()


# ══════════════════════════════════════════════════════════════════════════════
# _utils — backend / environment detection
# ══════════════════════════════════════════════════════════════════════════════

class TestVizUtils:

    def test_agg_is_not_interactive(self, monkeypatch):
        monkeypatch.setattr(matplotlib, "get_backend", lambda: "Agg")
        assert _utils.is_interactive_backend() is False

    @pytest.mark.parametrize("backend", ["TkAgg", "QtAgg", "MacOSX"])
    def test_interactive_backends_detected(self, monkeypatch, backend):
        monkeypatch.setattr(matplotlib, "get_backend", lambda: backend)
        assert _utils.is_interactive_backend() is True

    def test_is_notebook_reflects_cached_env(self, monkeypatch):
        monkeypatch.setattr(_utils, "_ENV", "jupyter")
        assert _utils.is_notebook() is True
        monkeypatch.setattr(_utils, "_ENV", "headless")
        assert _utils.is_notebook() is False
        monkeypatch.setattr(_utils, "_ENV", "colab")
        assert _utils.is_notebook() is True

    def test_detect_environment_headless_in_pytest(self):
        # pytest runs without an IPython kernel — both ImportError and
        # get_ipython() is None resolve to 'headless'
        assert _utils._detect_environment() in ("headless", "ipython")

    def test_detect_environment_jupyter_shell(self, monkeypatch):
        class ZMQInteractiveShell:
            pass

        import IPython
        monkeypatch.setattr(
            IPython, "get_ipython", lambda: ZMQInteractiveShell()
        )
        assert _utils._detect_environment() == "jupyter"

    def test_detect_environment_terminal_shell(self, monkeypatch):
        class TerminalInteractiveShell:
            pass

        import IPython
        monkeypatch.setattr(
            IPython, "get_ipython", lambda: TerminalInteractiveShell()
        )
        assert _utils._detect_environment() == "ipython"

    def test_detect_environment_colab(self, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "google.colab", object())
        assert _utils._detect_environment() == "colab"
