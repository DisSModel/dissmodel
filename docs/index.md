
# DisSModel

**Discrete Spatial Modeling framework for Python**

DisSModel is a modular, production-ready Python framework for spatially explicit dynamic modeling. Developed by the [LambdaGeo](https://github.com/DisSModel) group at the Federal University of Maranhão (UFMA), it provides a unified environment for building **Cellular Automata (CA)** and **System Dynamics (SysDyn)** models.

Inspired by the [TerraME](http://www.terrame.org/) framework, DisSModel brings the same modeling expressiveness to Python — replacing the TerraLib/Lua stack with GeoPandas and NumPy, while remaining fully interoperable with the broader Python data science ecosystem.

```bash
pip install dissmodel
```

---

## Architecture

DisSModel is organized into five core modules designed for reproducibility and scalability:

| Module | Description |
|:---|:---|
| `dissmodel.core` | Simulation clock and execution lifecycle. |
| `dissmodel.geo` | Spatial substrates — Dual-design (Vector + Raster) for flexible modeling. |
| `dissmodel.executor` | **(New)** Standardized execution layer for CLI and Remote Workers. |
| `dissmodel.io` | **(New)** Storage-agnostic I/O handling local files and MinIO/S3. |
| `dissmodel.visualization` | Observer-based visualization — `Chart`, `Map`, `RasterMap`, `display_inputs`. |

---

## Dual Substrate Performance

The `geo` module provides two independent spatial substrates:

- **Vector substrate** (`geo.vector`): Backed by GeoPandas. Ideal for irregular geometries and GIS joins.
- **Raster substrate** (`geo.raster`): Backed by NumPy. Fully vectorized operations (up to **4,500× faster** than vector at scale).

| Feature | Vector | Raster |
|---|---|---|
| Data structure | GeoDataFrame | NumPy 2D array |
| Neighbourhood | Queen / Rook (libpysal) | Moore / Von Neumann (vectorized) |
| Best for | GIS Interoperability | Large grids / High performance |

---

## Quickstart: System Dynamics

This example uses the SIR model from
[dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn)
(`pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"`):

```python
from dissmodel.core import Environment
from dissmodel_sysdyn.models import SIR
from dissmodel.visualization import Chart

env = Environment()
SIR(susceptible=9998, infected=2, recovered=0, contacts=6, probability=0.25)
Chart(show_legend=True)
env.run(30)
```

---

## 📦 Model Ecosystem

To keep the core framework lean, we maintain specialized libraries containing ready-to-use models. These are excellent starting points for your own research:

- [**DisSModel-CA**](https://github.com/DisSModel/dissmodel-ca): A collection of Cellular Automata models including Game of Life, Forest Fire, and Growth models.
- [**DisSModel-SysDyn**](https://github.com/DisSModel/dissmodel-sysdyn): System Dynamics implementations such as SIR, Predator-Prey, and the Lorenz Attractor.

---


## License

MIT © 2026 Sérgio Costa & Nerval Santos Junior — [LambdaGeo/UFMA](https://github.com/DisSModel)