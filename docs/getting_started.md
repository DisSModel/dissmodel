# Getting Started

## Installation

```bash
pip install dissmodel
```

For development mode (tests and dev tooling — mypy, ruff, pytest, docs):

```bash
git clone https://github.com/DisSModel/dissmodel
cd dissmodel
pip install -e ".[dev]"
```

Runnable example models (cellular automata, system dynamics) live in the
satellite repositories [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca)
and [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn):

```bash
pip install "git+https://github.com/DisSModel/dissmodel-ca.git"
pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"
```

---

## Instantiation Order

The `Environment` is the heart of the simulation. It must always be created **before** any model.

```text
Environment  →  Model  →  Visualization  →  env.run()
     ↑             ↑            ↑                ↑
  Step 1        Step 2        Step 3           Step 4
```

---

## Execution Modes

DisSModel supports three main ways to interact with your models:

### 1. Command Line (CLI)
Standardized via the `dissmodel.executor`. Best for batch experiments and
experiment tracking. Ready-to-run CLI scripts ship with the satellite
repositories — for example, from a clone of
[dissmodel-ca](https://github.com/DisSModel/dissmodel-ca):

```bash
git clone https://github.com/DisSModel/dissmodel-ca.git
cd dissmodel-ca
pip install .
python examples/cli/ca_game_of_life.py
```

### 2. Jupyter Notebooks
Best for teaching and incremental analysis. DisSModel renders visualizations
inline automatically. See the executed notebooks in this documentation under
[Examples → Notebooks](examples/notebooks/ca_game_of_life.ipynb), or the
larger educational collections in the satellite repositories.

### 3. Streamlit Apps
Reactive web interfaces with zero boilerplate. Parameters are automatically
mapped to sidebar widgets. From a clone of `dissmodel-ca`:

```bash
streamlit run examples/streamlit/ca_all.py
```

---

## Your first reproducible experiment

This walkthrough takes about five minutes and needs nothing but DisSModel. It
uses a forest fire, a small cellular automaton, so you can see what a
*reproducible* run means before meeting a real model. The `verify`,
`reproduce` and `compare` commands arrive in version 0.7.

```bash
pip install "dissmodel>=0.7"
```

The files below are in
[`examples/hello_reproducible`](https://github.com/DisSModel/dissmodel/tree/main/examples/hello_reproducible) together with a `run.sh` that runs
every command in order, and the repository tests run them.

### 1. The model: science only

`forest_fire_model.py` has no file reading or writing. It says how a cell
changes from one step to the next, and nothing else.

```python
# forest_fire_model.py
import numpy as np
from dissmodel.geo import SyncRasterModel

FOREST, BURNING, BURNED = 0, 1, 2


class ForestFire(SyncRasterModel):
    def setup(self, backend, prob_spread=0.4, seed=42):
        super().setup(backend)
        self.land_use_types = ["state"]       # bands kept as state_past
        self.prob_spread = prob_spread
        self.rng = np.random.default_rng(seed)

    def execute(self):                        # once per step: only maths, no I/O
        past = self.backend.get("state_past")
        burning_neighbours = self.backend.focal_sum_mask(past == BURNING)
        catch = (past == FOREST) & (
            self.rng.random(self.shape) < 1 - (1 - self.prob_spread) ** burning_neighbours
        )
        state = past.copy()
        state[catch] = BURNING
        state[past == BURNING] = BURNED
        self.backend.arrays["state"] = state
```

### 2. The executor: everything that is not science

The executor says where the data comes from, where the result goes and what
is recorded. The seed is a parameter here, so it ends up in the record.

```python
# my_executor.py
from dissmodel.core import Environment
from dissmodel.executor import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io import load_dataset, save_dataset

from forest_fire_model import ForestFire


class ForestFireExecutor(ModelExecutor):
    name = "forest_fire"
    output_suffix = ".tif"

    def load(self, record: ExperimentRecord):
        (backend, _meta), checksum = load_dataset(record.source.uri)
        record.source.checksum = checksum
        return backend

    def run(self, data, record: ExperimentRecord):
        p = record.parameters
        env = Environment(end_time=p.get("end_time", 60))
        ForestFire(backend=data, prob_spread=p.get("prob_spread", 0.4), seed=p.get("seed", 42))
        env.run()
        return data

    def save(self, result, record: ExperimentRecord) -> ExperimentRecord:
        uri = record.output_path or "output.tif"
        record.output_sha256 = save_dataset(result, uri)
        record.output_path = uri
        record.status = "completed"
        return record


if __name__ == "__main__":
    run_cli(ForestFireExecutor)
```

### 3. The input: a forest with one fire

```python
# make_input.py
from dissmodel.geo import raster_grid
from dissmodel.io import save_dataset

grid = raster_grid(rows=100, cols=100, attrs={"state": 0})   # 0 = forest
grid.arrays["state"][50, 50] = 1                             # 1 = burning
save_dataset(grid, "forest.tif")
```

```bash
python make_input.py
```

### 4. Run it

Parameters live in a TOML file and can be overridden on the command line.

```toml
# model.toml
[model.parameters]
end_time = 60
prob_spread = 0.4
seed = 42
```

```bash
python my_executor.py run --input forest.tif --output result.tif \
                          --toml model.toml --preserve-output-name
```

Without `--preserve-output-name`, DisSModel adds a short experiment ID to the
name (`result_83bc068f.tif`), so two runs never overwrite each other. Here the
names stay fixed to keep the commands below short. The run leaves three files:

| File | What it is |
|---|---|
| `result.tif` | the output |
| `result.record.json` | the record: parameters, the resolved TOML, SHA-256 of input and output, versions, environment and timings |
| `profiling_<id>.md` | time spent in each phase |

### 5. Check that the output is the one in the record

```bash
dissmodel verify result.record.json
```

```text
✓ result.tif matches the record (7e7ab1e5f81049a6…)
```

This catches a file that was edited, truncated or swapped after the run. The
hash on your machine may differ from the one above: how a GeoTIFF is encoded
depends on the GDAL build, which is why step 7 compares decoded values too.

### 6. Repeat the run

```bash
dissmodel reproduce result.record.json --module my_executor
```

```text
<id>: identical (bytes identical, decoded values identical, georeference identical)
record: result.repro.record.json
```

`reproduce` runs the model again from what the record stored (the resolved
parameters and the input path) and compares the new output with the original.
`--module` tells it where to find your executor; the command looks for it in
the current folder. For an executor that comes from an installed package (for
example DisSLUCC), the record already says where it is and the option is not
needed.

### 7. See a difference

Change one parameter and run again:

```bash
python my_executor.py run --input forest.tif --output other.tif \
                          --toml model.toml --param prob_spread=0.5 --preserve-output-name
dissmodel compare result.tif other.tif
```

```text
result.tif: differs (bytes DIFFERS, decoded values DIFFERS, georeference identical)
```

The command exits with status 1 whenever the verdict is not acceptable, so it
can stop a Makefile or a CI job.

| Verdict | Meaning |
|---|---|
| `identical` | the files are the same, byte for byte |
| `values_identical` | different bytes (for example another compression from another GDAL build), same values, same position |
| `equivalent` | values differ, but by no more than a tolerance **you declared** with `--atol` |
| `differs` | different values, or a raster that moved (transform, CRS or nodata) |
| `unverified` | something that mattered could not be checked (unreadable file, rasterio missing) |

`equivalent` never appears on its own: it needs `--atol`, for example
`dissmodel compare a.tif b.tif --atol 1e-9`. The tolerance is a statement
about your model, so DisSModel does not guess it.

### What the record does not capture

- **Your script.** For a loose script the record says `model_commit: "local-cli"`
  and the DisSModel version, and nothing identifies `forest_fire_model.py`
  itself. If you change the model and reproduce, the verdict is `differs` but
  the record cannot say why. Keep the script in git, and commit before each
  run you want to cite. An executor installed from a package records the
  package and its version (for example `disslucc==0.5.0`).
- **Where you were.** The record keeps the input path as you typed it. With a
  relative path, run `dissmodel reproduce` from the same folder, or use
  absolute paths (or `s3://` URIs) from the start.
- **Anything the executor reads outside the record.** Parameters, the input
  file and the TOML are recorded. A file the model opens by itself, or the
  current time, are not.

### Where to go next

- A real model with this same structure: [DisSLUCC](https://github.com/DisSModel/disslucc).
- Run it by name, in a queue, with results in object storage: [DisSModel Platform](https://github.com/DisSModel/dissmodel-platform).

---

## Storage & Reproducibility
Since version 0.2.0, DisSModel can read and write directly to **MinIO/S3**. Every execution via the standard CLI generates a `record.json` and a profiling report, ensuring your science is always traceable.
