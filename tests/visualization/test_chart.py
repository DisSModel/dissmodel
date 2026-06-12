"""
tests/visualization/test_chart.py
==================================
Tests for dissmodel.visualization.chart — track_plot decorator and the
Chart component.

All rendering paths are exercised headlessly (Agg backend):
- headless save_frames (PNG per step)
- Streamlit path (fake plot_area)
- notebook path with and without an anchored Output widget
- select= filtering and styling options (legend, grid, title)
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from dissmodel.core import Environment, Model
from dissmodel.visualization.chart import Chart, track_plot


# ── helper model with tracked attributes ──────────────────────────────────────

@track_plot(label="Infected", color="red")
@track_plot(label="Recovered", color="green")
class SIR(Model):
    def setup(self):
        self.infected  = 100
        self.recovered = 0

    def execute(self):
        self.infected  -= 10
        self.recovered += 10


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.fixture(autouse=True)
def fresh_plot_info():
    """track_plot stores data buffers on the class — reset between tests."""
    for info in SIR._plot_info.values():
        info["data"] = []
    yield


# ══════════════════════════════════════════════════════════════════════════════
# track_plot decorator
# ══════════════════════════════════════════════════════════════════════════════

class TestTrackPlot:

    def test_registers_plot_info_per_label(self):
        assert set(SIR._plot_info) == {"infected", "recovered"}
        assert SIR._plot_info["infected"]["color"] == "red"
        assert SIR._plot_info["infected"]["plot_type"] == "line"

    def test_attribute_assignment_appends_to_buffer(self):
        Environment(start_time=0, end_time=1)
        model = SIR()
        model.infected = 90
        # setup() assigned 100, then 90
        assert SIR._plot_info["infected"]["data"][-2:] == [100, 90]

    def test_tracked_labels_registered_in_environment(self):
        env = Environment(start_time=0, end_time=1)
        SIR()
        assert "Infected" in env._plot_metadata
        assert "Recovered" in env._plot_metadata


# ══════════════════════════════════════════════════════════════════════════════
# Chart — setup and rendering
# ══════════════════════════════════════════════════════════════════════════════

class TestChartSetup:

    def test_defaults(self):
        Environment(start_time=0, end_time=1)
        chart = Chart()
        assert chart.select is None
        assert chart.show_legend is True
        assert chart.show_grid is False
        assert chart.title == "Variable History"
        assert chart.fig is not None  # created outside notebooks

    def test_custom_options(self):
        Environment(start_time=0, end_time=1)
        chart = Chart(
            select=["Infected"],
            show_legend=False,
            show_grid=True,
            title="SIR",
            pause=False,
        )
        assert chart.select == ["Infected"]
        assert chart.title == "SIR"


class TestChartRender:

    def _env_with_data(self, **chart_kwargs):
        env = Environment(start_time=0, end_time=2)
        SIR()
        chart = Chart(pause=False, **chart_kwargs)
        return env, chart

    def test_render_plots_all_tracked_variables(self):
        env, chart = self._env_with_data(show_grid=True)
        env.run()
        # one line per tracked label
        labels = [line.get_label() for line in chart.ax.get_lines()]
        assert "Infected" in labels and "Recovered" in labels

    def test_select_filters_variables(self):
        env, chart = self._env_with_data(select=["Infected"])
        env.run()
        labels = [line.get_label() for line in chart.ax.get_lines()]
        assert "Infected" in labels
        assert "Recovered" not in labels

    def test_time_points_accumulate(self):
        env, chart = self._env_with_data()
        env.run()
        assert len(chart.time_points) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Chart — execution targets
# ══════════════════════════════════════════════════════════════════════════════

class TestChartExecuteTargets:

    def test_headless_save_frames_writes_png(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        env = Environment(start_time=0, end_time=2)
        SIR()
        Chart(save_frames=True, pause=False)
        env.run()

        frames = sorted((tmp_path / "chart_frames").glob("chart_step_*.png"))
        assert len(frames) >= 1

    def test_headless_without_save_frames_still_saves_on_agg(
        self, tmp_path, monkeypatch
    ):
        # Agg is not an interactive backend → falls into _save_frame branch
        monkeypatch.chdir(tmp_path)
        env = Environment(start_time=0, end_time=1)
        SIR()
        Chart(save_frames=False, pause=False)
        env.run()
        assert (tmp_path / "chart_frames").exists()

    def test_streamlit_plot_area_receives_figure(self):
        class FakePlotArea:
            def __init__(self):
                self.figures = []

            def pyplot(self, fig):
                self.figures.append(fig)

        area = FakePlotArea()
        env = Environment(start_time=0, end_time=2)
        SIR()
        Chart(plot_area=area, pause=False)
        env.run()
        assert len(area.figures) >= 1

    def test_notebook_path_with_anchored_widget(self, monkeypatch):
        monkeypatch.setattr(
            "dissmodel.visualization.chart.is_notebook", lambda: True
        )
        env = Environment(start_time=0, end_time=1)
        SIR()
        chart = Chart(pause=False)

        if chart._out is None:
            pytest.skip("ipywidgets not installed — fallback covered elsewhere")
        env.run()  # must not raise

    def test_notebook_path_without_widget_uses_image_fallback(self, monkeypatch):
        import sys
        monkeypatch.setattr(
            "dissmodel.visualization.chart.is_notebook", lambda: True
        )
        monkeypatch.setitem(sys.modules, "ipywidgets", None)
        env = Environment(start_time=0, end_time=1)
        SIR()
        chart = Chart(pause=False)
        assert chart._out is None
        env.run()  # exercises clear_output + Image fallback without raising
