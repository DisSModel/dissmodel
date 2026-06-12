---
title: "DisSModel: A Python Framework for Spatially Explicit Dynamic Modeling"
tags:
  - Python
  - Geographic Information Systems
  - Dynamic Spatial Modeling
  - Cellular Automata
  - Land Use and Cover Change (LUCC)
  - Time-Stepped Simulation
authors:
  - name: Sérgio Souza Costa
    orcid: 0000-0002-0232-4549
    affiliation: "1"
  - name: Nerval de Jesus Santos Junior
    affiliation: "1"
    orcid: 0009-0000-2339-3191
  - name: Felipe Martins Sousa
    affiliation: "1"
    orcid: 0009-0009-0505-4845
  - name: José Magno Pinheiro Alves
    affiliation: "1"
    orcid: 0009-0003-7212-4870
  - name: Denilson da Silva Bezerra
    affiliation: "1"
    orcid: 0000-0002-9567-7828


affiliations:
  - name: Universidade Federal do Maranhão (UFMA)
    index: "1"
    city: São Luís
    state: MA
    country: Brazil
date: 12 April 2026
bibliography: paper.bib
---

## Summary

DisSModel (Discrete Spatial Modeling) is a modular Python framework designed for
spatially explicit dynamic modeling, specifically targeting the complexities of
Land Use and Land Cover Change (LUCC). Developed to bridge the gap between static
geospatial analysis and high-level dynamic simulations, DisSModel translates the
modeling paradigms of the TerraME framework [@Carneiro2013] into the Python
ecosystem. It enables researchers to simulate complex socio-environmental
systems — including forest fires, epidemiological spreads, and coastal dynamics —
by coupling a time-stepped simulation clock with the spatial data structures of
GeoPandas [@Jordahl2021].

The framework provides a **dual-substrate architecture**: a vector substrate backed
by GeoDataFrame for flexibility and spatial expressiveness, and a raster substrate
backed by NumPy 2D arrays for high-performance vectorised computation. DisSModel is
available through the DisSModel GitHub organisation and on PyPI.

## Statement of Need

In the Geographic Information Systems (GIS) landscape, Python has become the lingua
franca for data science, supported by libraries such as GeoPandas for vector
manipulation and PySAL for spatial statistics. However, these tools are primarily
designed for static analysis. Dynamic spatial modeling — simulating how landscapes
evolve over time — has historically required specialised platforms like TerraME
[@Carneiro2013] or Dinamica EGO.

While TerraME is conceptually robust, the requirement for Lua scripting creates a
barrier for data scientists already invested in the Python ecosystem. Furthermore,
general-purpose simulation libraries lack native "glue code" to synchronise a
time-stepped simulation clock with the geographical state of a GeoDataFrame.
DisSModel fulfils this need with a lightweight, purpose-built time-stepped
scheduler coupled directly to vector and raster spatial state, providing a
Pythonic implementation of the TerraME
paradigm, democratising access to complex modeling for territorial planners and
environmental scientists. It offers native support for hybrid data
types — Geo-fields and Geo-objects — allowing for simulations that remain
interoperable with modern machine learning and GIS workflows.

Beyond simulation execution, reproducibility is a first-class concern in DisSModel.
The `executor` module provides a standardised lifecycle — `validate → load → run → save`
— that captures provenance metadata (input checksums, parameters, timing, output
paths) in an `ExperimentRecord` object automatically generated for every run. This
design ensures that results produced locally or via CLI are fully traceable without
additional instrumentation by the modeller.

## State of the Field

DisSModel occupies a unique niche between general-purpose agent-based modeling (ABM)
libraries and specialised GIS simulation software. The following table highlights
its positioning:

| Aspect | TerraME | Dinamica EGO | DisSModel |
|--------|---------|--------------|-----------|
| Language | Lua | Visual/Internal | Python |
| Simulation Engine | Discrete Event | Cellular Automata | Time-stepped scheduler |
| Spatial Structure | CellularSpace (Fixed) | Cellular Grid | GeoDataFrame + NumPy (Dual) |
| GIS Integration | TerraLib | Native Raster | GeoPandas / Rasterio |
| Extensibility | Script-based | Block-based | Class Inheritance |
| Reproducibility | Manual | Manual | Automated (ExperimentRecord) |
| Neighborhoods | GPM Support | Limited | libpysal weights (Queen, Rook, KNN, custom) |

While frameworks like **NetLogo** and **Mesa** are excellent for ABM, they often
require significant boilerplate to handle real-world spatial projections. DisSModel
simplifies this by using GeoPandas as its core engine, following the discrete
spatial modeling approach proposed by @SantosJunior2025.

## Software Design

DisSModel is organised into five modules, following a strict separation of concerns
that allows researchers to extend the framework through class inheritance.

**Core** manages the simulation clock and time-stepped execution. The `Environment`
class orchestrates time progression via a lightweight pure-Python scheduler, and all
spatial models auto-register at instantiation, receiving clock ticks automatically
through `setup / pre_execute / execute / post_execute` lifecycle hooks.

**Geo** manages spatial representations through a dual-substrate design. The vector
substrate (`vector_grid`, `SpatialModel`, `CellularAutomaton`) operates on
GeoDataFrame structures with libpysal neighbourhoods [@Rey2021]. The raster
substrate (`raster_grid`, `RasterModel`, `RasterCellularAutomaton`) operates on
named NumPy arrays via `RasterBackend`, enabling fully vectorised spatial
operations — `shift2d`, `focal_sum`, and `neighbor_contact` — that replace
cell-by-cell iteration loops.

**Executor** provides the standardised interface for packaging, deploying, and
reproducing simulations. The `ModelExecutor` abstract base class defines a four-phase
lifecycle — `validate`, `load`, `run`, `save` — that the framework orchestrates via
`execute_lifecycle`. Subclasses register themselves automatically in
`ExecutorRegistry` through Python's `__init_subclass__` mechanism, requiring no
boilerplate. Every execution produces an `ExperimentRecord` Pydantic object capturing
the input URI, SHA-256 checksum, resolved parameters, per-phase timing, output path,
and free-form logs. Executors are distributed as standard Python packages, with run
parameters resolved from a version-controllable TOML specification.

**IO** provides a unified dataset abstraction (`load_dataset` / `save_dataset`) that
detects format automatically and dispatches to the appropriate backend —
GeoDataFrame, rasterio GeoTIFF, or Xarray/Zarr — based on file extension or an
explicit `fmt` argument. For cloud deployments, the same API resolves
`s3://` URIs transparently via the configured MinIO/S3 client.

**Visualization** integrates Matplotlib for static outputs, Streamlit-compatible
input widgets (interactive dashboards are provided by the satellite packages), and
`RasterMap` for step-by-step raster rendering in both headless and interactive
modes.

The extensibility of DisSModel's class hierarchy has already produced domain
packages distributed as independent Python packages through the DisSModel GitHub
organisation. `dissmodel-ca` [@DisSModelCA] provides
ready-to-use Cellular Automata patterns built on `RasterCellularAutomaton`.
`dissmodel-sysdyn` [@DisSModelSysDyn] adds System Dynamics compartmental models as
first-class DisSModel components. `DisSLUCC-Continuous` [@DisSLUCCContinuous]
implements the continuous LUCC modeling components of the LUCCME framework — Demand,
Potential, and Allocation — following the three-pillar architecture proposed by
@Veldkamp1996 and @Verburg2004, on both vector and raster substrates and following
the same `ModelExecutor` contract. This last package establishes an explicit Python
counterpart to the original TerraME/LUCCME stack, where DisSModel occupies the role
of TerraME and DisSLUCC-Continuous occupies the role of LUCCME. All three packages
serve as reference implementations for researchers building their own domain
extensions.

## Performance

The dual-substrate design exposes a fundamental performance trade-off. The vector
substrate offers spatial expressiveness and direct integration with GIS workflows,
while the raster substrate achieves high throughput through NumPy vectorisation.

**Synthetic benchmark — Conway's Game of Life.** Running identical rules on both
substrates confirms that mathematical equivalence is preserved across substrates
while throughput scales differently:

| Grid | Cells | Raster (ms/step) | Vector (ms/step) | Speedup |
|-----:|------:|-----------------:|-----------------:|--------:|
| 10×10 | 100 | 0.15 | 30.11 | 206× |
| 50×50 | 2,500 | 0.20 | 647.22 | 3,164× |
| 100×100 | 10,000 | 0.60 | 2,715.16 | 4,491× |
| 500×500 | 250,000 | 15.36 | — | — |
| 1,000×1,000 | 1,000,000 | 25.85 | — | — |

The raster substrate processes grids of one million cells in approximately 26 ms per
step.

**Domain validation — BR-MANGUE coastal dynamics model.** The conceptual foundation
for coupled mangrove-flood modeling in Brazilian coastal zones was established by
Bezerra et al. [@Bezerra2013], who discussed the integration of remote sensing and
computational models to assess sea-level rise impacts on mangrove ecosystems. Building
on this framework, the `coastal-dynamics` package [@CoastalDynamics] implements
coupled flood and mangrove succession models over the same spatial domain on both
substrates. Outputs are categorical land-use and soil classes; match percentage is
therefore the appropriate primary metric [@Pontius2008]. Running 20 simulation steps
over a 60×60 synthetic grid (3,600 cells, EPSG:31984) produces the following results:

| Band | Match % | MAE | RMSE | Max Error | Cells |
|------|--------:|----:|-----:|----------:|------:|
| uso (land use) | 100.00% | 0.000000 | 0.000000 | 0.000000 | 3,600 |
| solo (soil)    | 100.00% | 0.000000 | 0.000000 | 0.000000 | 3,600 |
| alt (elevation)| 99.92%  | 0.003086 | 0.008362 | 0.072591  | 3,600 |

The raster substrate ran at 2.4 ms/step against 70.9 ms/step for the vector
substrate (29.7× speedup). The minor divergence in the elevation band (0.08% of
cells) reflects expected floating-point rounding differences between GeoDataFrame
and NumPy computation paths, not algorithmic disagreement. The `ExperimentRecord`
generated by this run captured the full execution provenance automatically:
load phase 2.898 s (49.4%), run phase 2.972 s (50.6%), input SHA-256 checksum,
and artifact paths — with zero additional instrumentation by the modeller.

**Domain validation — DisSLUCC-Continuous LUCC model.** The `DisSLUCC-Continuous`
package implements the continuous CLUE-like allocation algorithm [@Veldkamp1996],
in which each cell holds a fractional land-use proportion rather than a discrete
class. For continuous outputs, fixed-threshold match statistics are not meaningful for
real-valued spatial data [@Pontius2008]; MAE is the appropriate primary metric,
as it provides a directly interpretable measure of average model error [@Willmott2005]. Running 6 simulation steps over the Lab1 study area (6,574 cells)
and comparing against a TerraME/LUCCME reference result produces the following:

| Comparison | MAE | RMSE | Max Error | Cells |
|---|----:|-----:|----------:|------:|
| Vector vs TerraME | 0.003583 | 0.006188 | 0.027355 | 6,574 |
| Raster vs TerraME | 0.003583 | 0.006188 | 0.027355 | 6,574 |
| Vector vs Raster  | 0.000000 | 0.000000 | 0.000000 | 6,574 |

Both substrates reproduce the TerraME/LUCCME reference with a MAE of 0.0036 in
[0,1] scale — consistent with expected floating-point divergence between independent
Lua and Python implementations of the same continuous allocation algorithm. Vector
and raster substrates are numerically identical (MAE = 0.000), confirming that the
3.6× performance gain of the raster substrate (39.9 ms/step vs 143.2 ms/step)
introduces no algorithmic divergence.

## Research Impact Statement

DisSModel provides a critical bridge for the environmental modeling community. By
providing a Pythonic interface for complex spatial dynamics, it lowers the barrier
for scientists to move from static GIS analysis to dynamic simulations. The
framework has already been instrumental in academic research at the **LambdaGeo**
group (UFMA), supporting studies on mangrove ecosystem dynamics and land-use change,
building upon established spatial modeling practices [@Verburg2004; @SantosJunior2025].

The emergence of independent domain packages — `dissmodel-ca`, `dissmodel-sysdyn`,
`DisSLUCC-Continuous`, and `coastal-dynamics` — without modifications to the core
framework demonstrates that the `ModelExecutor` contract is stable and sufficient for
real-world modeling requirements. This is further evidenced by the DisSModel
Platform, a separate distributed execution environment currently under development that
already orchestrates both `DisSLUCC-Continuous` and `coastal-dynamics` in a shared
test infrastructure, running each through the same job queue without any change to
their scientific code. The platform validates the central design principle of
DisSModel: that simulation science should not need to be rewritten to run in
production.

This architecture positions DisSModel as the simulation layer in the Brazilian Earth
Observation stack — complementary to SITS [@Simoes2021] for present-state land
classification and the Brazil Data Cube [@Ferreira2020] for satellite data access.

## AI Usage Disclosure

This submission used generative AI tools (Claude Sonnet 4.6, NotebookLM, and Google
Jules) to assist with structuring documentation, synthesising prior work, and
generating submission checklists. All outputs were reviewed and validated by the
human authors.

## References
