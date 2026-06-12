
# Examples & Recipes

This page provides minimal, self-contained examples to demonstrate the core features of the DisSModel framework. These "recipes" are designed to help you quickly understand the mechanics of execution, spatial initialization, and visualization.

---

## ⚙️ Core Behavior: Multi-Model Timing

In DisSModel, each model can have its own execution window (active period), independent of the environment's global time range. This allows for complex simulations where different processes start or stop at different stages.

```python
from __future__ import annotations
from dissmodel.core import Environment, Model

class ModelA(Model):
    """Active from 2012 to environment end_time."""
    def execute(self) -> None:
        print(f"[A] time: {self.env.now()}")

class ModelB(Model):
    """Active from environment start_time to 2013."""
    def execute(self) -> None:
        print(f"[B] time: {self.env.now()}")

class ModelC(Model):
    """Active for the full environment duration."""
    def execute(self) -> None:
        print(f"[C] time: {self.env.now()}")

# Setup Environment (2010 - 2016)
env = Environment(start_time=2010, end_time=2016)

ModelA(start_time=2012)   # Joins the simulation later
ModelB(end_time=2013)     # Retires early
ModelC()                  # Default behavior (full duration)

env.run()
```

---

## 🗺️ Geospatial Operations

### Fill Strategy: RANDOM_SAMPLE

This recipe shows how to populate a grid attribute with values sampled from a probability distribution. It is a common pattern for initializing landscape states.

```python
import matplotlib.pyplot as plt
from dissmodel.geo import FillStrategy, fill, vector_grid

# Create a 5x5 grid
grid = vector_grid(dimension=(5, 5), resolution=1.0)

# Apply a random distribution
fill(
    strategy=FillStrategy.RANDOM_SAMPLE,
    gdf=grid,
    attr="risk",
    data={
        "low":    0.2,
        "medium": 0.5,
        "high":   0.3,
    },
    seed=42,
)

# Visualize the result
grid.plot(column="risk", legend=True)
plt.title("Risk distribution (RANDOM_SAMPLE)")
plt.show()
```

### Visualizing a GeoDataFrame with Map

DisSModel leverages GeoPandas, so any `GeoDataFrame` — built in code or
loaded from disk with `gpd.read_file(...)` — can be rendered with the
built-in observer-based `Map` component. This self-contained example
builds a small grid and displays it:

```python
from dissmodel.core import Environment
from dissmodel.geo import FillStrategy, fill, vector_grid
from dissmodel.visualization.map import Map

# Build a GeoDataFrame (swap for gpd.read_file("your_data.gpkg") to use real data)
gdf = vector_grid(dimension=(10, 10), resolution=1.0)
fill(
    strategy=FillStrategy.RANDOM_SAMPLE,
    gdf=gdf,
    attr="state",
    data={"forest": 0.7, "cleared": 0.3},
    seed=42,
)

env = Environment(start_time=0, end_time=0)

# Render the data using the framework's observer-based Map
Map(
    gdf=gdf,
    plot_params={"column": "state", "edgecolor": "black", "linewidth": 0.5},
)

env.run()
```

---

## 📂 Model Libraries

The DisSModel ecosystem is organized into specialized libraries. Each repository contains advanced implementations and research-ready models:

### 🔬 [DisSModel-CA](https://github.com/DisSModel/dissmodel-ca)
A collection of **Cellular Automata** models, including:
* **Game of Life** (Vector and Raster backends)
* **FireModel** (Forest fire propagation)
* **Growth** (Stochastic radial expansion)
* **Snow** (Accumulation and gravity dynamics)

### 📈 [DisSModel-SysDyn](https://github.com/DisSModel/dissmodel-sysdyn)
Implementations of classic **System Dynamics** models:
* **SIR** (Epidemiological modeling)
* **Predator-Prey** (Ecological population dynamics)
* **Lorenz Attractor** (Deterministic chaos)
* **Coffee Cooling** (Newton's Law of Cooling)

### 🌊 [BR-MANGUE](https://github.com/DisSModel/brmangue-dissmodel)
The BR-MANGUE coastal dynamics model, demonstrating model equivalence between vector and raster substrates — validated against the original TerraME implementation — for:
* **Mangrove Succession**
* **Coastal Flooding** (Flood models)

---

## 🚀 Execution Modes

You can run examples in different environments depending on your needs:

* **Command Line**: Best for performance and automation — see
  [CLI Examples](examples/cli.md).
* **Jupyter Notebooks**: Executed notebooks are rendered in this
  documentation under
  [Examples → Notebooks](examples/notebooks/ca_game_of_life.ipynb),
  ideal for step-by-step interactive exploration.
* **Streamlit**: From a clone of
  [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca), run
  `streamlit run examples/streamlit/ca_all.py` to explore models with a
  reactive UI — see [Streamlit Examples](examples/streamlit.md).

