"""
dissmodel/visualization/map.py
================================
Visualization component for GeoDataFrame — choropleth map rendered at
every simulation step.

Supported render targets
------------------------
1. **Streamlit**   — ``plot_area=st.empty()``
2. **Jupyter**     — detected automatically
3. **Colab**       — detected automatically
4. **Interactive** — matplotlib window (TkAgg / Qt)
5. **Headless**    — saves PNGs to ``map_frames/`` (default fallback)
"""
from __future__ import annotations

import pathlib
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.figure
import matplotlib.axes
import geopandas as gpd

from dissmodel.core import Model
from dissmodel.visualization._utils import is_interactive_backend, is_notebook


class Map(Model):
    """
    Simulation model that renders a live choropleth map of a GeoDataFrame.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame to render.
    plot_params : dict
        Keyword arguments forwarded to :meth:`GeoDataFrame.plot`.
    figsize : tuple[int, int]
        Figure size in inches. Default: ``(10, 6)``.
    pause : bool
        Call ``plt.pause()`` after each update in interactive mode.
    interval : float
        Seconds passed to ``plt.pause()``. Default: ``0.01``.
    plot_area : st.empty() | None
        Streamlit placeholder. Default: ``None``.
    save_frames : bool
        Save one PNG per step to ``map_frames/``. Default: ``False``.

    Examples
    --------
    >>> env = Environment(end_time=10)
    >>> Map(gdf=grid, plot_params={"column": "state", "cmap": "viridis"})
    >>> env.run()
    """

    # Narrowing the base Model.setup(**kwargs) contract is intentional:
    # Model.__init__ forwards extra kwargs to setup, and each component
    # declares the keywords it accepts.
    def setup(  # type: ignore[override]
        self,
        gdf:         gpd.GeoDataFrame,
        plot_params: dict[str, Any],
        figsize:     tuple[int, int] = (10, 6),
        pause:       bool            = True,
        interval:    float           = 0.01,
        plot_area:   Any             = None,
        save_frames: bool            = False,
    ) -> None:
        self.gdf         = gdf
        self.plot_params = plot_params
        self.figsize     = figsize
        self.pause       = pause
        self.interval    = interval
        self.plot_area   = plot_area
        self.save_frames = save_frames

        # widget Output ancorado — elimina blink no Jupyter/Colab
        # criado uma vez no setup; display() a seguir fixa a posição na célula
        self._out = None
        if is_notebook():
            try:
                import ipywidgets as widgets
                from IPython.display import display
                self._out = widgets.Output()
                display(self._out)
            except ImportError:
                pass  # ipywidgets ausente — cai no fallback clear_output

        # always create fig so _render() can always call self.fig.clf()
        self.fig, self.ax = plt.subplots(1, 1, figsize=self.figsize)

        # close immediately if not needed for interactive mode
        if is_notebook() or plot_area is not None:
            plt.close(self.fig)

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self, step: float) -> matplotlib.figure.Figure:
        if is_notebook() or self.plot_area is not None:
            # create a fresh figure every step
            self.fig, self.ax = plt.subplots(1, 1, figsize=self.figsize)
        else:
            # reuse existing figure — clear and redraw
            self.fig.clf()
            self.ax = self.fig.add_subplot(1, 1, 1)

        self.gdf.plot(ax=self.ax, **self.plot_params)
        self.ax.set_title(f"Map — Step {int(step)}")
        plt.tight_layout()
        plt.draw()
        return self.fig

    def _save_frame(self, fig: matplotlib.figure.Figure, step: float) -> None:
        col     = self.plot_params.get("column", "map")
        out_dir = pathlib.Path("map_frames")
        out_dir.mkdir(exist_ok=True)
        fname = out_dir / f"{col}_step_{int(step):03d}.png"
        fig.savefig(fname, dpi=100, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        end_time = getattr(self.env, "end_time", step)
        if int(step) % 10 == 0 or step == end_time:
            print(f"  Map [{col}] step {int(step):3d} → {fname}")

    # ── execute ───────────────────────────────────────────────────────────────

    def execute(self) -> None:
        step = self.env.now()
        fig  = self._render(step)

        if self.plot_area is not None:
            # Streamlit
            self.plot_area.pyplot(fig)
            plt.close(fig)

        elif is_notebook():
            from IPython.display import clear_output, display
            if self._out is not None:
                # Output widget ancorado — sem blink
                with self._out:
                    clear_output(wait=True)
                    display(fig)
            else:
                # fallback: ipywidgets ausente
                clear_output(wait=True)
                display(fig)
            plt.close(fig)

        elif self.save_frames or not is_interactive_backend():
            # headless / CI
            self._save_frame(fig, step)

        else:
            # interactive window
            if self.pause:
                plt.pause(self.interval)
            end_time = getattr(self.env, "end_time", step)
            if step == end_time:
                plt.show()
