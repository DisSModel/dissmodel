
# DisSModel 🌍

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![PyPI version](https://badge.fury.io/py/dissmodel.svg)](https://pypi.org/project/dissmodel/)
[![Coverage](https://img.shields.io/badge/coverage-79%25-orange.svg)](https://github.com/DisSModel/dissmodel/actions)
[![DisSModel](https://img.shields.io/badge/LambdaGeo-Research-green.svg)](https://github.com/DisSModel)
[![JOSS Status](https://joss.theoj.org/papers/46522bc30d2dbec6b509d2dc487170ec/status.svg)](https://joss.theoj.org/papers/46522bc30d2dbec6b509d2dc487170ec)

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
| — | `brmangue-dissmodel` | Coastal domain models (BR-MANGUE) built on dissmodel |
| **TerraLib** | `geopandas` / `rasterio` | Geographic data handling |

---

## 🌟 Key Features

- **Dual substrate** — same model logic runs on vector (`GeoDataFrame`) and raster (`RasterBackend`/NumPy).
- **Lightweight scheduler** — pure-Python time-stepped engine; models auto-register at instantiation and receive clock ticks via `setup / pre_execute / execute / post_execute` lifecycle hooks.
- **Executor pattern** — strict separation between science (models) and infrastructure (I/O, CLI, reproducible execution).
- **Experiment tracking** — every run generates an immutable `ExperimentRecord` with SHA-256 checksums, TOML snapshot, and full provenance.
- **Storage-agnostic I/O** — `dissmodel.io` handles local paths and `s3://` URIs transparently.
- **Platform-ready contract** — the `ModelExecutor` interface is designed so the same model code can later run on the [DisSModel Platform](#-roadmap-dissmodel-platform), a separate project under development.

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
from dissmodel.core import Environment
from dissmodel.geo import SpatialModel, vector_grid

# 10x10 grid where every cell starts as forest
gdf = vector_grid(dimension=(10, 10), resolution=1.0, attrs={"state": "forest"})

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

### 5. Cloud storage (s3://)

Any `s3://bucket/key` URI works transparently anywhere dissmodel accepts a
path — the CLI's `--input`/`--output`, `load_dataset`/`save_dataset`,
`load_geotiff`/`save_geotiff` — so a model can read or write straight from
object storage with no code changes:

```bash
python my_executor.py run \
  --input s3://forest-data/scenes/forest.gpkg \
  --output s3://forest-data/results/result.gpkg \
  --toml model.toml
```

This is a standalone data-access feature, not tied to the rest of the
`dissmodel-platform` stack — it works against any S3-compatible endpoint:
a bare MinIO server you run yourself, AWS S3, or anything else that speaks
the S3 protocol.

Install the extra and configure the endpoint through environment variables:

```bash
pip install dissmodel[s3]

export MINIO_ENDPOINT=localhost:9000      # host:port, no scheme
export MINIO_ACCESS_KEY=your-access-key
export MINIO_SECRET_KEY=your-secret-key
export MINIO_SECURE=1                     # unset/empty for plain HTTP (e.g. local dev)
```

No further setup is required — `s3://` URIs are resolved lazily, so nothing
above is needed for runs that only use local paths.

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

The `record.json` written next to every output contains everything needed to
re-run the experiment: the input URI and its SHA-256 checksum, the resolved
parameters (TOML + CLI overrides), per-phase timings, and the output checksum.

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

The map below shows how the pieces fit together, and how each one relates to its counterpart in INPE's TerraME ecosystem, which DisSModel takes as its conceptual basis. It is an early snapshot: the `dissmodel` core is the most mature piece, and the other packages are still taking shape.

<p align="center">
  <img src="https://raw.githubusercontent.com/DisSModel/dissmodel/main/docs/assets/images/dissmodel_ecosystem.svg" alt="DisSModel ecosystem map: TerraME is the conceptual basis for the dissmodel core; TerraME's CA, system dynamics and agent-based packages correspond to dissmodel-ca, dissmodel-sysdyn and dissmodel-abm; LuccME corresponds to disslucc; fillCell corresponds to disscube; haloexec and dissmodel-platform are new infrastructure with no TerraME counterpart" width="100%">
</p>

### 🔬 Specialized Model Libraries

| Repository | Description | Install |
|------------|-------------|---------|
| [`dissmodel-ca`](https://github.com/DisSModel/dissmodel-ca) | Classic Cellular Automata (Game of Life, Forest Fire, Growth) | `pip install "git+https://github.com/DisSModel/dissmodel-ca.git"` |
| [`dissmodel-sysdyn`](https://github.com/DisSModel/dissmodel-sysdyn) | System Dynamics (SIR, Predator-Prey, Lorenz) | `pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"` |
| [`brmangue-dissmodel`](https://github.com/DisSModel/brmangue-dissmodel) | BR-MANGUE coastal flooding and mangrove succession model (raster + vector, validated against TerraME) | `pip install "git+https://github.com/DisSModel/brmangue-dissmodel.git"` |
| [`disslucc`](https://github.com/DisSModel/disslucc) | Land Use and Cover Change models, continuous and discrete allocation (CLUE-inspired), raster-only | `pip install "git+https://github.com/DisSModel/disslucc.git"` |

### 🛠 Implementation Templates

Each repository demonstrates how to:
1. **Define a Model**: Using `SpatialModel` and `Environment`.
2. **Wrap an Executor**: Using `ModelExecutor` for I/O and provenance.
3. **Deploy**: Running via CLI or API.

---

## 🔭 Roadmap: DisSModel Platform

The **DisSModel Platform** is a distributed execution environment (FastAPI,
Redis, Docker, MinIO/S3) currently under development as a **separate project**.
It consumes the same `ModelExecutor` contract documented above — executors run
through its job queue without any change to their scientific code, including
remote experiment reproduction from a stored `ExperimentRecord`.

**The platform is not part of this package.** Everything described in this
README works locally with `pip install dissmodel` alone.

---

## 📚 Documentation

- 📘 **User Guide**: [https://dissmodel.github.io/dissmodel/](https://dissmodel.github.io/dissmodel/)
- 🧪 **API Reference**: [https://dissmodel.github.io/dissmodel/api/core/](https://dissmodel.github.io/dissmodel/api/core/)
- 🎓 **Examples**: [https://dissmodel.github.io/dissmodel/examples/](https://dissmodel.github.io/dissmodel/examples/)

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

- 🐛 Report bugs → [GitHub Issues](https://github.com/DisSModel/dissmodel/issues)
- 💡 Request features → [GitHub Issues](https://github.com/DisSModel/dissmodel/issues)
- 📝 Improve docs → Fork, edit, and submit a PR

---

## 🎓 Citation

```bibtex
@software{dissmodel2026,
  author = {Costa, Sérgio Souza and Santos Junior, Nerval de Jesus and Sousa, Felipe Martins and Bezerra, Denilson da Silva},
  title = {DisSModel: A Python Framework for Spatially Explicit Dynamic Modeling},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/DisSModel/dissmodel},
  version = {0.6.5}
}
```

---

## ⚖️ License

MIT © [DisSModel — UFMA](https://github.com/DisSModel)  
See [LICENSE](LICENSE) for details.
