# Visualization

The `dissmodel.visualization` module provides graphical and interactive representations
of running simulations. All visualization components inherit from `Model` and are
therefore integrated into the simulation clock — they update automatically at each step.

Three main components are available:

| Component | Substrate | Description |
|-----------|-----------|-------------|
| `Chart` | Any | Time-series plots from tracked model variables |
| `Map` | Vector (GeoDataFrame) | Dynamic spatial maps updated each step |
| `RasterMap` | Raster (NumPy) | Raster array rendering — categorical or continuous |

All three support **three output targets**: local `matplotlib` window,
Jupyter inline display, and Streamlit `st.empty()` placeholder.

---

## `@track_plot`

The `track_plot` decorator marks model attributes to be collected and plotted
by `Chart`. Each call defines the variable label, colour, and plot type.

```python
from dissmodel.core import Model
from dissmodel.visualization import track_plot

@track_plot("Susceptible", "green")
@track_plot("Infected",    "red")
@track_plot("Recovered",   "blue")
class SIR(Model):

    def setup(self, susceptible=9998, infected=2, recovered=0,
              duration=2, contacts=6, probability=0.25):
        self.susceptible = susceptible
        self.infected    = infected
        self.recovered   = recovered
        self.duration    = duration
        self.contacts    = contacts
        self.probability = probability

    def execute(self):
        total   = self.susceptible + self.infected + self.recovered
        alpha   = self.contacts * self.probability
        new_inf = self.infected * alpha * (self.susceptible / total)
        new_rec = self.infected / self.duration
        self.susceptible -= new_inf
        self.infected    += new_inf - new_rec
        self.recovered   += new_rec
```

---

## `Chart`

Displays time-series data from variables annotated with `@track_plot`.

```python
from dissmodel.core import Environment
# SIR ships with dissmodel-sysdyn:
# pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"
from dissmodel_sysdyn.models import SIR
from dissmodel.visualization import Chart

env = Environment(end_time=30)
SIR()
Chart(show_legend=True)
env.run()
```

**Streamlit:**

```python
Chart(plot_area=st.empty())
```

---

## `Map`

Renders spatial data from a GeoDataFrame, updated at every simulation step.

```python
from dissmodel.visualization.map  import Map
from matplotlib.colors import ListedColormap

Map(
    gdf=gdf,
    plot_params={
        "column": "state",
        "cmap": ListedColormap(["white", "black"]),
        "ec": "gray",
    },
)
```

---

## `RasterMap`

Renders a named NumPy array from a `RasterBackend`. Supports categorical
(value → colour mapping) and continuous (colormap + colorbar) modes.

**Categorical:**

```python
from dissmodel.visualization.raster_map import RasterMap

RasterMap(
    backend   = b,
    band      = "uso",
    title     = "Land Use",
    color_map = {1: "#006400", 3: "#00008b", 5: "#d2b48c"},
    labels    = {1: "Mangrove", 3: "Sea", 5: "Bare soil"},
)
```

**Continuous:**

```python
RasterMap(
    backend        = b,
    band           = "alt",
    title          = "Altimetry",
    cmap           = "terrain",
    colorbar_label = "Altitude (m)",
    mask_band      = "uso",
    mask_value     = 3,      # mask SEA cells
)
```

**Headless** (default when no display is available):
frames are saved to `raster_map_frames/<band>_step_NNN.png`.

---

## `display_inputs`

Generates Streamlit input widgets automatically from a model's type annotations.
Integer and float attributes become sliders; booleans become checkboxes.

```python
from dissmodel.visualization import display_inputs

sir = SIR()
display_inputs(sir, st.sidebar)
```

---

## Full Streamlit example

```python
import streamlit as st
from dissmodel.core import Environment
# SIR ships with dissmodel-sysdyn:
# pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"
from dissmodel_sysdyn.models import SIR
from dissmodel.visualization import Chart, display_inputs

st.set_page_config(page_title="SIR Model", layout="centered")
st.title("SIR Model — DisSModel")

st.sidebar.title("Parameters")
steps   = st.sidebar.slider("Steps", min_value=1, max_value=50, value=10)
run_btn = st.button("Run")

env = Environment(end_time=steps, start_time=0)
sir = SIR()
display_inputs(sir, st.sidebar)
Chart(plot_area=st.empty())

if run_btn:
    env.run()
```

---

## API Reference

::: dissmodel.visualization.chart.Chart

::: dissmodel.visualization.map.Map

::: dissmodel.visualization.raster_map.RasterMap