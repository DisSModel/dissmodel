# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed
- `load_geotiff` sets `RasterBackend.transform` and `RasterBackend.crs` from
  the file (they were only in the returned `meta` dict), and `save_geotiff`
  falls back to them: `save_geotiff(backend, uri)` writes a georeferenced
  GeoTIFF without a `meta` dict. Explicit `crs`/`transform` arguments still
  override `meta`, and `meta` overrides the backend.

### Added
- `RasterBackend.cell_area()`: the area of each cell from `transform` and
  `crs` — square metres on the ellipsoid for a geographic CRS (a 1/12° cell
  is ~86 km² at the equator and ~72 km² at 33° S), the pixel area for a
  projected one.

## [0.6.5] — 2026-09-22

### Fixed
- `CONTRIBUTING.md`: two `git clone` commands under "External Contributors"
  and "Development Setup" had unrendered Markdown link syntax pasted
  directly inside their `bash` code fences (`git clone [url](url)`),
  breaking the command if copy-pasted as written. Replaced with plain
  URLs.
- `CONTRIBUTING.md`: the License section linked to a Google search result
  (`https://www.google.com/search?q=LICENSE&utm_source=gemini`) instead of
  the repository's own `LICENSE` file. Replaced with a relative link.
- `README.md`: the `disslucc` row in the "Specialized Model Libraries"
  table still pointed to `LambdaGeo/disslucc`, while the other three rows
  and `paper.bib`'s `@DisSLUCC` entry already point to
  `DisSModel/disslucc` (the two currently resolve to the same commit via
  GitHub's repository-transfer redirect, but the README was left
  inconsistent by the 0.6.4 consolidation). Now points to
  `DisSModel/disslucc` consistently.
- `pyproject.toml`: `scipy` is now a declared direct dependency
  (`scipy>=1.12.0`). `dissmodel/geo/raster/backend.py`'s
  `neighbor_contact` has imported `scipy.ndimage.binary_dilation`
  unconditionally since it was written, but `scipy` only ever reached an
  environment as a transitive pull through `libpysal`; a `libpysal`
  release that drops or relaxes that pin could have broken `import
  dissmodel` with no dependency of ours saying why.
- `pyproject.toml`: added the `s3` extra (`minio>=7.0`).
  `dissmodel/io/_storage.py` has told users to run
  `pip install dissmodel[platform]` since it was written, in both its
  module docstring and its `ImportError` message, but that extra never
  existed — `pip install -e ".[platform]"` silently no-ops with a
  `does not provide the extra 'platform'` warning instead of installing
  `minio`, so following the tool's own instructions left S3/MinIO
  support still missing. Named `s3` rather than `platform`: this extra
  only pulls in the `minio` client used by the `s3://` URI helpers in
  `io/raster.py`, `io/vector.py`, `io/_utils.py`, and
  `executor/model_executor.py`/`executor/utils.py` — it talks to any
  S3-compatible endpoint via `MINIO_ENDPOINT`/`MINIO_ACCESS_KEY`/etc. and
  has no dependency on the rest of the `dissmodel-platform` stack
  (FastAPI, Jupyter, Redis), so naming it after that package was
  misleading. `_storage.py`'s docstring and `ImportError` message now
  say `pip install dissmodel[s3]`.
- `README.md`: added a "Cloud storage (s3://)" section under Quick Start.
  The `s3://` URI mechanism was already visible in the `ExperimentRecord`
  JSON example (`"source": {"uri": "s3://...", ...}`) but never explained
  — there was no installation, configuration, or usage guidance anywhere
  in the README for a feature that works standalone, from the CLI, with
  no dependency on the rest of `dissmodel-platform`.

### Added
- `tests/io/test_s3_real.py`: integration tests running a real `minio`
  client against a real (in-process, Docker-free) S3-protocol server —
  moto's `ThreadedMotoServer`. Every existing `s3://` test used
  `FakeMinioClient`, an in-memory stand-in that only implements
  `get_object`/`put_object`; it never exercised
  `ModelExecutor._resolve_uri` (the CLI's `--input s3://...` /
  `--output s3://...` path), which calls `minio.fget_object` — a method
  the fake doesn't have. That path had zero test coverage until now.
  New `dev`-extra dependencies: `minio>=7.0`, `moto[s3,server]>=5.0`.

### Internal
- Fixed all 81 lint findings surfaced by ruff 0.16.8's default rule set
  (unsorted imports, `Optional`/`Union` → `X | None`/`X | Y`, unsorted
  `__all__`, redundant `int | float` → `float`, merged `startswith` calls,
  a collapsible `if`, a mutable class-attribute default → `ClassVar`).
  Eight blind `except Exception` sites are intentional best-effort
  fallbacks (optional CRS/transform recovery, Colab widget setup, a
  test harness that must report rather than crash) and are now annotated
  with `# noqa` and a one-line rationale instead of silently tripping the
  linter.
- `pyproject.toml`: pinned `ruff>=0.16,<0.17` in `dev` extras and rewrote
  the `[tool.ruff]` comment, which claimed the project lints against a
  narrow "pyflakes + pycodestyle" baseline — that was already stale
  against ruff 0.16.8's actual (wider) default rule set, which is what
  produced the 81 findings above with no code changes on our side. The
  comment now describes the real default and the pin keeps it from
  drifting again on a routine `ruff` upgrade.
- `dissmodel/executor/registry.py` and `dissmodel/executor/testing.py`:
  their `TYPE_CHECKING`-only import of `ModelExecutor` pointed at
  `dissmodel.core.base`, a module that doesn't exist — silently masked by
  `ignore_missing_imports = true` in `[tool.mypy]`, which also covers
  first-party unresolvable imports, not just third-party ones. Both now
  import from `dissmodel.executor.model_executor`, the actual location;
  `ModelExecutor` in these two files' type hints stops resolving to `Any`.
  No runtime effect (both imports were `TYPE_CHECKING`-guarded), and mypy
  still reports no issues now that the type is real.
- `pyproject.toml`: removed the top-level `ignore_missing_imports = true`
  from `[tool.mypy]` — it's exactly what let the `dissmodel.core.base`
  mismatch above go unnoticed, since it silences unresolvable first-party
  imports the same as untyped third-party ones. The per-module override
  list (already there for `geopandas`, `shapely`, etc.) now also covers
  `scipy`, `minio`, `google.colab`, and `ipywidgets` — all genuinely
  stub-less — so mypy stays clean on the same grounds as before, but a
  future typo in one of *our* import paths won't have anywhere left to
  hide.
- `.github/workflows/ci.yml`: two independent config drifts that
  bypassed the fixes above at CI time, found while adding
  `test_s3_real.py`. The `lint` job installed `ruff` with no version
  constraint, defeating the `pyproject.toml` pin's whole purpose of
  keeping the default rule set from silently growing again — now
  installs the same pinned `ruff>=0.16,<0.17`. The `test` job ran
  `mypy dissmodel --ignore-missing-imports`, a CLI flag that overrides
  `[tool.mypy]` entirely regardless of its per-module override list —
  reintroducing, at the CI level, the exact blanket-ignore risk just
  removed from `pyproject.toml` above. The flag is now gone; CI runs
  plain `mypy dissmodel`.

---

## [0.6.4] — 2026-09-22

### Fixed
- `dissmodel.executor.cli`: local `--toml` runs now merge `[model]`-level
  spec keys (e.g. `land_use_types`, `[[model.potential_data]]`) into
  `record.parameters`, not just `[model.parameters]`. Previously, any
  model registered the same way as `dissmodel-configs`/
  `dissmodel-platform` (registration metadata and spec at the `[model]`
  level, `[model.parameters]` reserved for run-specific overrides) ran
  locally via `--toml` with most of its required parameters silently
  missing (#176, #177).

### Internal
- `paper.md` / `paper.bib`: consolidated citations of `disslucc-continuous`
  and `disslucc-discrete` into a single `disslucc` citation, reflecting
  their merge into one repository. `README.md`'s specialized model
  libraries table follows the same consolidation.

---

## [0.6.3] — 2026-07-16

### Fixed
- `mypy` config: bumped `python_version` to `3.12` so NumPy 2.x stubs parse
  correctly, and added the missing type annotations in `RasterBackend` and
  `dissmodel.io.raster` that the stricter parse surfaced.

### Changed
- README badges: refreshed the coverage badge (55% → 79%, stale since 0.6.1)
  and renamed the `LambdaGeo` badge label to `DisSModel`.

### Internal
- JOSS paper (`paper.md` / `paper.bib`) revised in response to reviewer
  feedback (openjournals/joss-reviews#10827): added a CRediT-style
  contribution statement for all five authors, expanded the Research Impact
  Statement and AI Usage Disclosure, corrected reproducibility pointers and
  several bibliography entries, and trimmed the body text to fit the JOSS
  1,750-word limit.

---

## [0.6.2] — 2026-06-15

### Fixed
- `SyncRasterModel.synchronize()`: state variables loaded as temporal
  `(time, y, x)` arrays (e.g. when `CubeClient.to_lucc_data()` finds
  temporal catalog entries) now correctly use the first slice as the
  initial `_past` snapshot instead of copying the full 3D array, which
  caused `shift2d` to crash with `ValueError: too many values to unpack`.
- `_write_geotiff`: casting a float array containing NaN to an integer
  `dtype` (e.g. `int16`) now fills NaN/inf with the band's `nodata` value
  before the cast, eliminating a `RuntimeWarning: invalid value encountered
  in cast`.

---

## [0.6.1] — 2026-06-12

### Fixed
- GeoTIFF write with mixed-dtype `band_spec` (e.g. int32 categorical +
  float32 continuous) silently truncated float bands to the first band's
  dtype. Bands are now promoted to the common NumPy result type
  (`np.result_type`) before writing.

### Added
- Test suites for `dissmodel.io` (utils, dispatch, storage, raster, vector,
  convert, xarray) and `dissmodel.visualization` (chart, map, env detection).
  Coverage: 55% → 79% (319 → 441 tests).

### Notes
- GeoTIFFs containing mixed-dtype bands saved with v0.6.0 may have truncated
  float bands. Re-exporting those files is recommended.

---

## [0.6.0] — 2026-06-11

### Breaking Changes
- `Environment.run()`: `end_time` is now **inclusive** (TerraME-style) — the
  simulation executes every scheduled tick `t` with
  `start_time <= t <= end_time`. A model's own `end_time` is inclusive as well.
  **Migration:** if you previously used `end_time=N_STEPS` expecting `N_STEPS`
  executions starting at 0, use `end_time=N_STEPS-1`.

### Added
- `RasterBackend`: temporal `(time, y, x)` variable support — `set(name, arr,
  time=coords)` / `get(name, time=t)` (ceiling lookup via `searchsorted`,
  clamped at the boundaries), `is_temporal`, `time_axis`, and the
  `temporal_band_names()` / `static_band_names()` partition helpers;
  `from_xarray` / `to_xarray` import and export temporal variables with their
  time coordinates preserved. This is the integration substrate for DisSCube's
  `CubeClient.to_lucc_data()`
- `ExperimentRecord.period`: optional `(start, end)` temporal window recording
  which cube slices fed the simulation (provenance/reproducibility)

### Fixed
- `ExperimentRecord.created_at`: deprecated `datetime.utcnow` replaced by
  `datetime.now(timezone.utc)` — timestamps are now timezone-aware (ISO
  serialization gains a `+00:00` offset)
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
