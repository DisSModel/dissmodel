# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] — 2026-06-11

### Breaking Changes
- `Environment.run()`: `end_time` is now **inclusive** (TerraME-style) — the
  simulation executes every scheduled tick `t` with
  `start_time <= t <= end_time`. A model's own `end_time` is inclusive as well.
  **Migration:** if you previously used `end_time=N_STEPS` expecting `N_STEPS`
  executions starting at 0, use `end_time=N_STEPS-1`.

### Fixed
- `RasterBackend.from_xarray`: fixed Affine transform reconstruction when
  rebuilding a backend from an `xarray.Dataset`
- Scheduler: clock no longer stalls when models finish before the
  environment's `end_time` (carried over from the unreleased 0.5.x line)

### Changed
- Version is now single-sourced from package metadata
  (`importlib.metadata.version`); `dissmodel.__version__`, `pyproject.toml`,
  `CITATION.cff` and the README citation no longer drift apart
- README: ecosystem table now uses `pip install "git+https://…"` install
  commands for satellite libraries not yet published on PyPI, and repository
  links were fixed to point to existing repositories
- README citation (BibTeX) aligned with `CITATION.cff` and the JOSS paper
  author list

### Internal
- `mypy dissmodel --ignore-missing-imports` is now clean (0 errors)

---

## [0.5.0] — 2026-05-02

### Breaking Changes
- Removed `salabim` and `greenlet` dependencies entirely
- `Model.process()` no longer exists — replace with `pre_execute()` / `post_execute()` hooks

### Added
- `Environment`: lightweight pure-Python time-stepped scheduler
- `Model.setup(**kwargs)`: called automatically at instantiation, mirrors salabim `Component.setup()` contract
- `Model.pre_execute()`: hook called before each `execute()`
- `Model.post_execute()`: hook called after each `execute()`

### Changed
- `SyncRasterModel`: replaced `process()` with `pre_execute()` / `post_execute()`
- `SyncSpatialModel`: replaced `process()` with `pre_execute()` / `post_execute()`
- `Environment.run()`: loop now calls `pre_execute → execute → post_execute` per model per tick

### Removed
- `salabim>=25.0.0` from dependencies
- `greenlet>=3.0.0` from dependencies
- `salabim.*` from mypy overrides

### Internal
- Public API unchanged — existing models implementing only `execute()` require no modification
---

## [0.3.0] - 2026-04

### Added

#### Sync models
- `SyncSpatialModel` — `SpatialModel` with automatic `_past` snapshot semantics,
  equivalent to TerraME's `cs:synchronize()`. Declare `self.land_use_types` in
  `setup()` and `<col>_past` columns are managed automatically.
- `SyncRasterModel` — raster analogue of `SyncSpatialModel`. Copies each array in
  `land_use_types` to `<n>_past` in the `RasterBackend` before and after each step.
- Both expose a public `synchronize()` method that can also be called manually.

#### I/O — `dissmodel.geo.raster.io`
- `shapefile_to_raster_backend` — loads any GeoPandas-supported vector format
  (Shapefile, GeoJSON, GeoPackage, ZIP) and rasterizes attribute columns into a
  `RasterBackend`. Adds a `"mask"` band marking valid cells. Supports
  `nodata_value` to distinguish out-of-extent cells from valid zero values.
- `save_raster_backend` — convenience wrapper that writes all (or selected) arrays
  to a GeoTIFF without requiring a `band_spec`.
- `load_geotiff` and `save_geotiff` updated with full docstrings and support for
  `.zip` archives containing a single GeoTIFF.

#### `RasterMap`
- `scheme` parameter: `"manual"` (default), `"equal_interval"`, `"quantiles"`.
- `k` — number of colour classes for `equal_interval`. Default: `5`.
- `legend` — show or hide the colorbar. Default: `True`.
- `save_frames` — force PNG output even in interactive mode.
- `auto_mask` — automatically applies the `"mask"` band from the backend so
  out-of-extent cells are transparent. Default: `True`.

#### `Map`
- `figsize`, `interval`, `save_frames` parameters.
- Headless fallback: saves PNGs to `map_frames/` when no display is available.

### Changed
- `RasterMap` no longer calls `matplotlib.use()` at import time, preventing side
  effects when imported alongside other visualization components.
- `make_raster_grid()` renamed to `raster_grid()`. Old name kept as a
  `DeprecationWarning` alias and will be removed in v0.4.0.

### Fixed
- `Map`: fixed `AttributeError: 'Map' object has no attribute 'fig'` when used
  with Streamlit (`plot_area=st.empty()`).
- `Map`: no longer raises `RuntimeError` when no display is available — falls back
  to saving PNGs to `map_frames/`.
- `RasterMap`: fixed `plt.close("all")` closing all figures when multiple
  `RasterMap` instances are active. Each instance now maintains its own persistent
  figure and updates independently.

---

## [0.2.1] - 2026-03

### Changed
- `parse_idx` now returns `GridPos(row, col)` namedtuple instead of a plain tuple,
  eliminating the `(col, row)` vs `(row, col)` ambiguity. Tuple unpacking remains
  fully compatible — no breaking change for existing callers.
- `regular_grid()` renamed to `vector_grid()`. Old name kept as a `DeprecationWarning`
  alias and will be removed in v0.3.0.

### Added
- `GridPos` namedtuple exported from `dissmodel.geo.vector.regular_grid`.

### Fixed
- `RasterModel.setup()` and `RasterCellularAutomaton.setup()` no longer accept
  `**kwargs`, resolving a salabim incompatibility that raised
  `TypeError: parameter 'kwargs' not allowed`.

---

## [0.2.0] - 2026-03

### Added

#### Raster substrate
- `RasterBackend` — named NumPy array store with vectorized spatial operations:
  `shift2d`, `focal_sum`, `focal_sum_mask`, `neighbor_contact`, `snapshot`.
- `RasterModel` — base class for raster push models, providing `self.backend`,
  `self.shape`, `self.shift`, and `self.dirs` (Moore neighbourhood).
- `RasterCellularAutomaton` — vectorized CA base class; `rule(arrays) → dict`
  replaces per-cell iteration.
- `raster_grid()` / `make_raster_grid()` — `RasterBackend` factory.
- `DIRS_MOORE` and `DIRS_VON_NEUMANN` — neighbourhood direction constants.
- `RasterMap` — visualization component supporting categorical (`color_map`) and
  continuous (`cmap`) modes; renders to Streamlit, Jupyter, interactive window,
  or headless PNG frames.

#### Vector substrate
- `SpatialModel` — GeoDataFrame-based push model with `create_neighborhood()`,
  `neighs_id()`, `neighs()`, and `neighbor_values()`.
- `vector_grid()` — replaces `regular_grid()` as the canonical grid factory name.

#### Examples and benchmarks
- `GameOfLifeRaster` — Conway's Game of Life on raster substrate.
- `FireModelRaster` — forest fire spread on raster substrate.
- `benchmark_game_of_life.py` — vector vs raster benchmark with exact cell-by-cell
  validation; supports `--steps`, `--sizes`, `--no-validation` flags.
- `benchmark_raster_vs_vector.py` — flood model benchmark at realistic workload.
- CLI examples updated.

#### Tests
- Full test suite: `tests/vector/`, `tests/raster/`, `tests/integration/`.
- `tests/integration/test_game_of_life.py` — exact cell-by-cell validation across
  5×5, 10×10, 20×20 grids and 5 seeds.
- `tests/integration/test_flood_model.py` — cross-substrate equivalence with 95%
  match threshold.

### Changed
- Package reorganized: `dissmodel.geo.vector.*` and `dissmodel.geo.raster.*`
  replace the flat `dissmodel.geo.*` layout.
- Documentation migrated to MkDocs Material with separate API reference pages for
  vector and raster substrates.

### Fixed
- Import paths corrected across all examples after package reorganization.
- `celullar_automaton.py` filename typo fixed → `cellular_automaton.py`.

### Performance
Benchmarks on Conway's Game of Life (10 steps, Python 3.12, NumPy):

| Grid | Cells | Raster (ms/step) | Vector (ms/step) | Speedup |
|-----:|------:|-----------------:|-----------------:|--------:|
| 10×10 | 100 | 0.15 | 30.11 | 206× |
| 50×50 | 2,500 | 0.20 | 647.22 | 3,164× |
| 100×100 | 10,000 | 0.60 | 2,715.16 | 4,491× |
| 1,000×1,000 | 1,000,000 | 25.85 | — | — |

---

## [0.1.5] - 2026-02

### Added
- JOSS submission at this version.

### Fixed
- Minor documentation and packaging fixes.

---

## [0.1.0] - 2025

### Added
- Initial release.
- `CellularAutomaton` and `SpatialModel` on GeoDataFrame substrate.
- `regular_grid()`, `fill()`, `FillStrategy`.
- System Dynamics models: `SIR`, `PredatorPrey`, `PopulationGrowth`, `Lorenz`, `Coffee`.
- Cellular Automata models: `GameOfLife`, `FireModel`, `FireModelProb`, `Snow`, `Growth`,
  `Propagation`, `Anneal`.
- Salabim integration via `dissmodel.core.Environment` and `Model`.
- Streamlit examples.
