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

## Storage & Reproducibility
Since version 0.2.0, DisSModel can read and write directly to **MinIO/S3**. Every execution via the standard CLI generates a `record.json` and a profiling report, ensuring your science is always traceable.
