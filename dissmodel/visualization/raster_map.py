"""
dissmodel/visualization/raster_map.py
======================================
Visualization component for RasterBackend — the raster analogue of the
vector ``Map`` component in DisSModel.

Supported render targets
------------------------
1. **Streamlit**   — ``plot_area=st.empty()``
2. **Jupyter**     — detected automatically
3. **Colab**       — detected automatically
4. **Interactive** — matplotlib window (TkAgg / Qt), used when a display
                     is available
5. **Headless**    — saves PNGs to ``raster_map_frames/`` when no display
                     is detected or ``save_frames=True``

The component does NOT call ``matplotlib.use()`` at import time — the
backend is left to matplotlib's own detection. This prevents side effects
when ``RasterMap`` is imported alongside other visualization components
(e.g. via ``dissmodel.visualization.__init__``).

Usage examples
--------------
    # categorical
    RasterMap(backend=b, band="uso", color_map=COLORS, labels=LABELS)

    # continuous — paridade com Map vetorial
    # auto_mask=True (default) aplica o extent mask do backend automaticamente
    RasterMap(backend=b, band="f", cmap="Greens",
              scheme="equal_interval", k=5, legend=True)

    # continuous — vmin/vmax explícitos + mask de domínio (ex: mar na altimetria)
    RasterMap(backend=b, band="alt", cmap="terrain",
              vmin=0.0, vmax=100.0, colorbar_label="Altitude (m)",
              mask_band="uso", mask_value=3)

    # desligar auto_mask se quiser o comportamento pré-v2
    RasterMap(backend=b, band="f", auto_mask=False)

Extent mask automático
-----------------------
Quando ``auto_mask=True`` (default), o RasterMap consulta
``backend.nodata_mask`` antes de renderizar. Células fora do extent
ficam transparentes sem nenhuma configuração adicional.

O ``backend.nodata_mask`` é derivado automaticamente pelo RasterBackend:
  - se existe a banda ``"mask"``: True onde mask != 0
  - senão, usa ``nodata_value`` do backend sobre o primeiro array disponível
"""
from __future__ import annotations

import pathlib
from typing import Any

import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches

from dissmodel.core import Model
from dissmodel.visualization._utils import is_notebook, is_interactive_backend


def _get_nodata_mask(backend) -> np.ndarray | None:
    """
    Deriva a extent mask do backend sem exigir que o backend implemente
    um atributo específico — funciona com qualquer RasterBackend existente.

    Prioridade:
    1. backend.nodata_mask  — se o backend já expõe a propriedade
    2. arrays["mask"]       — convenção dissluc (mask != 0 = válido)
    3. nodata_value         — aplica sobre o primeiro array disponível
    """
    # 1. propriedade nativa (futura)
    if hasattr(backend, "nodata_mask"):
        mask = backend.nodata_mask
        if mask is not None:
            return mask

    arrays = getattr(backend, "arrays", {})

    # 2. banda "mask" — convenção dissluc
    if "mask" in arrays:
        return arrays["mask"] != 0

    # 3. nodata_value sobre o primeiro array
    nodata = getattr(backend, "nodata_value", None)
    if nodata is not None and arrays:
        first = next(iter(arrays.values()))
        return first != nodata

    return None


class RasterMap(Model):
    """
    Visualization model for RasterBackend.

    Parameters
    ----------
    backend : RasterBackend
    band : str
        Array to visualize.
    title : str
        Figure title prefix. Default: ``"RasterMap"``.
    figsize : tuple[int, int]
        Default: ``(7, 7)``.
    pause : bool
        Use ``plt.pause()`` in interactive mode. Default: ``True``.
    interval : float
        Seconds between steps in interactive mode. Default: ``0.5``.
    plot_area : st.empty() | None
        Streamlit placeholder.
    auto_mask : bool
        Apply the backend's extent mask automatically so pixels outside
        the study area are transparent. Default: ``True``.
        Set to ``False`` to restore the pre-v2 behaviour.

    Categorical mode  (``color_map`` provided)
    -------------------------------------------
    color_map : dict[int, str]
        ``{value: "#rrggbb"}``
    labels : dict[int, str]
        ``{value: "label"}`` — used in the legend.

    Continuous mode  (``color_map`` absent)
    ----------------------------------------
    cmap : str
        Matplotlib colormap name. Default: ``"viridis"``.
    scheme : str
        ``"manual"``         — use ``vmin`` / ``vmax`` (default).
        ``"equal_interval"`` — divide [min, max] of valid data into ``k`` classes.
        ``"quantiles"``      — p2–p98 of valid data, robust to outliers.
    k : int
        Number of colour classes for ``scheme="equal_interval"``. Default: ``5``.
    vmin, vmax : float | None
        Bounds for ``scheme="manual"``.
    legend : bool
        Show the colorbar. Default: ``True``.
    colorbar_label : str
        Colorbar label. Default: ``band``.
    mask_band : str | None
        Additional domain mask (e.g. mask sea cells for altimetry).
        Applied on top of the automatic extent mask.
    mask_value : int | float | None
        Value in ``mask_band`` to mask.
    """

    # Created lazily in _render so each instance owns its own figure.
    _fig: matplotlib.figure.Figure | None
    _ax: Any

    # Narrowing the base Model.setup(**kwargs) contract is intentional:
    # Model.__init__ forwards extra kwargs to setup, and each component
    # declares the keywords it accepts.
    def setup(  # type: ignore[override]
        self,
        backend,
        band:            str              = "state",
        title:           str              = "RasterMap",
        figsize:         tuple[int, int]  = (7, 7),
        pause:           bool             = True,
        interval:        float            = 0.5,
        plot_area:       Any              = None,
        auto_mask:       bool             = True,
        save_frames:     bool             = False,
        # categorical
        color_map:       dict[int, str] | None = None,
        labels:          dict[int, str] | None = None,
        # continuous
        cmap:            str              = "viridis",
        scheme:          str              = "manual",
        k:               int              = 5,
        vmin:            float | None     = None,
        vmax:            float | None     = None,
        legend:          bool             = True,
        colorbar_label:  str | None       = None,
        mask_band:       str | None       = None,
        mask_value:      int | float | None = None,
    ) -> None:
        self.backend        = backend
        self.band           = band
        self.title          = title
        self.figsize        = figsize
        self.pause          = pause
        self.interval       = interval
        self.plot_area      = plot_area
        self.auto_mask      = auto_mask
        self.save_frames    = save_frames
        self.color_map      = color_map
        self.labels         = labels or {}
        self.cmap           = cmap
        self.scheme         = scheme
        self.k              = k
        self.vmin           = vmin
        self.vmax           = vmax
        self.legend         = legend
        self.colorbar_label = colorbar_label or band
        self.mask_band      = mask_band
        self.mask_value     = mask_value

        # resolve extent mask once at setup — not on every frame
        self._extent_mask: np.ndarray | None = (
            _get_nodata_mask(backend) if auto_mask else None
        )

        # widget Output ancorado — elimina blink no Jupyter/Colab
        self._out = None
        if is_notebook():
            try:
                import ipywidgets as widgets
                from IPython.display import display
                self._out = widgets.Output()
                display(self._out)
            except ImportError:
                # ipywidgets is optional (pip install dissmodel[viz]);
                # without it the clear_output fallback path is used.
                pass

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self, step: float) -> matplotlib.figure.Figure:
        # each RasterMap owns its own figure — reuse across steps
        # so multiple instances show as separate windows simultaneously
        if not hasattr(self, "_fig") or self._fig is None \
                or not plt.fignum_exists(self._fig.number):
            self._fig, self._ax = plt.subplots(figsize=self.figsize)
        else:
            self._fig.clf()
            self._ax = self._fig.add_subplot(1, 1, 1)

        fig, ax = self._fig, self._ax

        arr = self.backend.arrays.get(self.band)
        if arr is None:
            ax.text(0.5, 0.5, f"band '{self.band}' not found",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_title(f"{self.title} [{self.band}] — Step {int(step)}")
            return fig

        if self.color_map:
            self._render_categorical(ax, arr, self.color_map)
        else:
            self._render_continuous(ax, arr)

        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f"{self.title} [{self.band}] — Step {int(step)}")
        plt.tight_layout()
        return fig

    def _apply_masks(self, data: np.ndarray) -> np.ma.MaskedArray:
        """
        Aplica todas as máscaras em ordem e retorna um MaskedArray:
        1. extent mask automático (auto_mask=True)
        2. mask_band / mask_value  (domínio, ex: mar para altimetria)
        3. NaN / Inf residuais
        """
        # 1. extent mask — pixels fora do estudo
        if self._extent_mask is not None:
            data = np.where(self._extent_mask, data, np.nan)

        # 2. domain mask — ex: mascarar mar na visualização de altimetria
        if self.mask_band is not None and self.mask_value is not None:
            mask_arr = self.backend.arrays.get(self.mask_band)
            if mask_arr is not None:
                data = np.where(mask_arr == self.mask_value, np.nan, data)

        # 3. cobre NaN / Inf (inclui os inseridos pelos passos acima)
        return np.ma.masked_invalid(data)

    def _render_categorical(
        self, ax, arr: np.ndarray, color_map: dict[int, str]
    ) -> None:
        vals = sorted(color_map)
        cmap = mcolors.ListedColormap([color_map[v] for v in vals])
        norm = mcolors.BoundaryNorm(
            [v - 0.5 for v in vals] + [vals[-1] + 0.5], cmap.N
        )
        cmap.set_bad(color="white", alpha=0)
        data = self._apply_masks(arr.astype(float))

        ax.imshow(data, cmap=cmap, norm=norm, aspect="equal", interpolation="nearest")

        present = set(np.unique(arr[~np.isnan(arr.astype(float))]))
        patches = [
            matplotlib.patches.Patch(color=color_map[v],
                                     label=self.labels.get(v, str(v)))
            for v in vals if v in present
        ]
        if patches:
            ax.legend(handles=patches, loc="lower right", fontsize=7, framealpha=0.7)

    def _render_continuous(self, ax, arr: np.ndarray) -> None:
        data  = self._apply_masks(arr.astype(float))
        cmap  = plt.get_cmap(self.cmap).copy()
        cmap.set_bad(color="white", alpha=0)

        valid = data.compressed()

        if len(valid) == 0:
            vmin, vmax = 0.0, 1.0

        elif self.scheme == "equal_interval":
            vmin = float(valid.min())
            vmax = float(valid.max())
            if vmin != vmax and self.k > 1:
                bounds = np.linspace(vmin, vmax, self.k + 1)
                norm   = mcolors.BoundaryNorm(bounds, plt.get_cmap(self.cmap).N)
                im = ax.imshow(data, cmap=cmap, norm=norm, aspect="equal",
                               interpolation="nearest")
                if self.legend:
                    plt.colorbar(im, ax=ax, label=self.colorbar_label,
                                 fraction=0.03, pad=0.02)
                return

        elif self.scheme == "quantiles":
            vmin = float(np.percentile(valid, 2))
            vmax = float(np.percentile(valid, 98))

        else:   # "manual"
            vmin = self.vmin if self.vmin is not None else float(valid.min())
            vmax = self.vmax if self.vmax is not None else float(valid.max())

        if vmin == vmax:
            vmax = vmin + 1.0

        im = ax.imshow(data, cmap=cmap, aspect="equal",
                       interpolation="nearest", vmin=vmin, vmax=vmax)
        if self.legend:
            plt.colorbar(im, ax=ax, label=self.colorbar_label,
                         fraction=0.03, pad=0.02)

    # ── execute ───────────────────────────────────────────────────────────────

    def execute(self) -> None:
        step = self.env.now()
        fig  = self._render(step)
        plt.draw()

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
            out_dir = pathlib.Path("raster_map_frames")
            out_dir.mkdir(exist_ok=True)
            fname = out_dir / f"{self.band}_step_{int(step):03d}.png"
            fig.savefig(fname, dpi=100, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
            plt.close(fig)
            end_time = getattr(self.env, "end_time", step)
            if int(step) % 10 == 0 or step == end_time:
                print(f"  RasterMap [{self.band}] step {int(step):3d} → {fname}")

        else:
            # interactive window
            if self.pause:
                plt.pause(self.interval)
            end_time = getattr(self.env, "end_time", step)
            if step == end_time:
                plt.show()
