
# DisSModel 🌍

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![PyPI version](https://badge.fury.io/py/dissmodel.svg)](https://pypi.org/project/dissmodel/)
[![LambdaGeo](https://img.shields.io/badge/LambdaGeo-Research-green.svg)](https://github.com/DisSModel)
[![JOSS Status](https://joss.theoj.org/papers/placeholder/status.svg)](https://joss.theoj.org)

> *"Science should not need to be rewritten to go into production."*  
> *(A ciência não deve ser reescrita para ir para a produção.)*

---

## 📖 Research Trajectory

**DisSModel did not emerge from a blank slate.** It is the current expression of a research agenda that began in 2001 with an undergraduate thesis on geographic data interoperability using XML and open standards — a time when the central question was already forming:

> *How can geospatial models be built so that others can understand, reuse, and trust them?*

| Period | Project | Contribution to the Agenda |
|--------|---------|---------------------------|
| **2001–2002** | Terra Translator (XML, ontologies) | Foundation: geographic data needs semantics and open standards |
| **2005** | TerraHS (Haskell + GIS) | Vision: scientific models as verifiable, executable artifacts |
| **2007–2010** | TerraME / LuccME (INPE) | Maturity: spatially explicit dynamic models as scientific objects |
| **2015–2024** | DbCells, Linked Data, QGIS plugins | Infrastructure: reproducibility demands rich metadata and federated access |
| **2024–2026** | **DisSModel** (Python, FAIR, cloud-native) | Synthesis: same code runs from Jupyter to distributed cluster |

Three principles unite this trajectory:
1. 🔓 **Openness as method** — open source and open data as conditions for scientific validation.
2. 🧩 **Interoperability as architecture** — systems designed to communicate, avoiding silos.
3. ♻️ **Reproducibility as requirement** — publishing conditions for re-execution, not just results.

DisSModel is the synthesis: a Python-native, FAIR-aligned, cloud-ready simulation framework where the same scientific code runs unchanged from a Jupyter notebook to a distributed production cluster.

---

## 🎯 About

**DisSModel** is a modular Python framework for spatially explicit dynamic simulation models. Developed by the [LambdaGeo](https://github.com/DisSModel) group at the Federal University of Maranhão (UFMA), it provides the simulation layer that connects domain models (LUCC, coastal dynamics) to a reproducible execution environment.

| INPE / TerraME Ecosystem | LambdaGeo Ecosystem | Role |
|--------------------------|---------------------|------|
| **TerraME** | `dissmodel` | Generic framework for dynamic spatial modeling |
| **LUCCME** | `DisSLUCC` | LUCC domain models built on dissmodel |
| — | `coastal-dynamics` | Coastal domain models built on dissmodel |
| **TerraLib** | `geopandas` / `rasterio` | Geographic data handling |

---

## 🌟 Key Features

- **Dual substrate** — same model logic runs on vector (`GeoDataFrame`) and raster (`RasterBackend`/NumPy).
- **Lightweight scheduler** — pure-Python time-stepped engine; models auto-register at instantiation and receive clock ticks via `setup / pre_execute / execute / post_execute` lifecycle hooks.
- **Executor pattern** — strict separation between science (models) and infrastructure (I/O, CLI, reproducible execution).
- **Experiment tracking** — every run generates an immutable `ExperimentRecord` with SHA-256 checksums, TOML snapshot, and full provenance.
- **Storage-agnostic I/O** — `dissmodel.io` handles local paths and `s3://` URIs transparently.
- **Cloud-ready** — deploy via Docker, FastAPI, and Redis without changing model code.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Science Layer  (Model)                                  │
│  FloodModel, AllocationClueLike, MangroveModel, ...      │
│  → only knows math, geometry and time                    │
├──────────────────────────────────────────────────────────┤
│  Infrastructure Layer  (ModelExecutor)                   │
│  CoastalRasterExecutor, LUCCVectorExecutor, ...          │
│  → only knows URIs, local/S3, column_map, parameters     │
├──────────────────────────────────────────────────────────┤
│  Core modules                                            │
│  dissmodel.core      — Environment, Model, SpatialModel  │
│  dissmodel.geo       — RasterBackend, neighborhoods      │
│  dissmodel.executor  — ModelExecutor ABC, ExperimentRecord│
│  dissmodel.io        — load_dataset / save_dataset       │
│  dissmodel.visualization — Map, RasterMap, Chart         │
└──────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install

```bash
pip install dissmodel

# Or latest development version
pip install "git+https://github.com/DisSModel/dissmodel.git@main"
```

### 2. Write a Model

```python
# forest_fire_model.py
from dissmodel.core import Environment, SpatialModel

class ForestFireModel(SpatialModel):
    def setup(self, prob_spread=0.3):
        self.prob_spread = prob_spread

    def execute(self):
        # Called every step — only math here, no I/O
        burning = self.gdf["state"] == "burning"
        # ... apply spread logic ...

env = Environment(end_time=50)
ForestFireModel(gdf=gdf, prob_spread=0.4)
env.run()
```

### 3. Wrap an Executor (for CLI + Provenance)

```python
# my_executor.py
from dissmodel.executor import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io import load_dataset, save_dataset

class ForestFireExecutor(ModelExecutor):
    name = "forest_fire"

    def load(self, record: ExperimentRecord):
        gdf, checksum = load_dataset(record.source.uri)
        record.source.checksum = checksum
        return gdf

    def run(self, data, record: ExperimentRecord):
        from dissmodel.core import Environment
        env = Environment(end_time=record.parameters.get("end_time", 50))
        ForestFireModel(gdf=data, **record.parameters)
        env.run()
        return data

    def save(self, result, record: ExperimentRecord) -> ExperimentRecord:
        uri = record.output_path or "output.gpkg"
        checksum = save_dataset(result, uri)
        record.output_path = uri
        record.output_sha256 = checksum
        record.status = "completed"
        return record

if __name__ == "__main__":
    run_cli(ForestFireExecutor)
```

### 4. Run via CLI

```bash
# Execute a simulation
python my_executor.py run \
  --input data/forest.gpkg \
  --output data/result.gpkg \
  --param end_time=50 \
  --toml model.toml

# Validate data contract without running
python my_executor.py validate --input data/forest.gpkg

# Show resolved parameters
python my_executor.py show --toml model.toml
```

---

## 📦 ExperimentRecord: Reproducibility by Design

Every run produces an immutable provenance record:

```json
{
  "experiment_id": "abc123",
  "model_commit": "a3f9c12",
  "code_version": "0.5.0",
  "resolved_spec": { "...TOML snapshot..." },
  "source": { "uri": "s3://...", "checksum": "e3b0c44..." },
  "artifacts": { "output": "sha256...", "profiling": "sha256..." },
  "metrics": { "time_run_sec": 2.15, "time_total_sec": 2.34 },
  "status": "completed"
}
```

Reproduce any past experiment exactly:

```bash
curl -X POST http://localhost:8000/experiments/abc123/reproduce \
  -H "X-API-Key: chave-sergio"
```

---

## 📊 Performance Telemetry

Every run via the executor lifecycle generates a `profiling_{id}.md` alongside the output:

| Phase | Time (s) | % Total | Memory Peak (MB) | I/O Ops |
|-------|----------|---------|-----------------|---------|
| **Validate** | 0.000 | 0.0% | 142 | 0 |
| **Load** | 0.306 | 14.7% | 387 | 12 (read) |
| **Run** | 1.025 | 49.4% | 521 | 0 |
| **Save** | 0.746 | 35.9% | 498 | 8 (write) |
| **Total** | **2.077** | **100%** | **521** | **20** |


---

## 🧩 Ecosystem: Models & Examples

DisSModel is a core framework. To maintain a clean and specialized environment, all simulation models and implementation examples are hosted in separate repositories within the DisSModel ecosystem.

### 🔬 Specialized Model Libraries

| Repository | Description | Install |
|------------|-------------|---------|
| [`DisSModel-CA`](https://github.com/DisSModel/dissmodel-ca) | Classic Cellular Automata (Game of Life, Forest Fire, Growth) | `pip install dissmodel-ca` |
| [`DisSModel-SysDyn`](https://github.com/DisSModel/dissmodel-sysdyn) | System Dynamics (SIR, Predator-Prey, Lorenz) | `pip install dissmodel-sysdyn` |
| [`coastal-dynamics`](https://github.com/DisSModel/coastal-dynamics) | Coastal flooding and mangrove succession models | `pip install coastal-dynamics` |
| [`DisSLUCC`](https://github.com/DisSModel/DisSLUCC) | Land Use and Cover Change models (CLUE-inspired) | `pip install disslucc` |

### 🛠 Implementation Templates

Each repository demonstrates how to:
1. **Define a Model**: Using `SpatialModel` and `Environment`.
2. **Wrap an Executor**: Using `ModelExecutor` for I/O and provenance.
3. **Deploy**: Running via CLI or API.

---

## 📚 Documentation

- 📘 **User Guide**: [https://dissmodel.github.io/dissmodel/](https://dissmodel.github.io/dissmodel/)
- 🧪 **API Reference**: [https://dissmodel.github.io/dissmodel/api/](https://dissmodel.github.io/dissmodel/api/)
- 🎓 **Tutorials**: [https://dissmodel.github.io/dissmodel/tutorials/](https://dissmodel.github.io/dissmodel/tutorials/)

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

- 🐛 Report bugs → [GitHub Issues](https://github.com/DisSModel/dissmodel/issues)
- 💡 Request features → [GitHub Discussions](https://github.com/DisSModel/dissmodel/discussions)
- 📝 Improve docs → Fork, edit, and submit a PR

---

## 🎓 Citation

```bibtex
@software{dissmodel2026,
  author = {Costa, Sérgio and Santos Junior, Nerval},
  title = {DisSModel: A Discrete Spatial Modeling Framework for Python},
  year = {2026},
  publisher = {LambdaGeo, Federal University of Maranhão (UFMA)},
  url = {https://github.com/DisSModel/dissmodel},
  version = {0.6.0}
}
```

---

## ⚖️ License

MIT © [DisSModel — UFMA](https://github.com/DisSModel)  
See [LICENSE](LICENSE) for details.
