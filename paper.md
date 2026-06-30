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

DisSModel (Discrete Spatial Modeling) is a modular Python framework for spatially
explicit dynamic modeling, targeting the complexities of Land Use and Land Cover
Change (LUCC). It translates the modeling paradigms of the TerraME framework
[@Carneiro2013] into the Python ecosystem, enabling researchers to simulate
complex socio-environmental systems — forest fires, epidemiological spreads,
coastal dynamics — by coupling a time-stepped simulation clock with the spatial
data structures of GeoPandas [@Jordahl2021].

The framework provides a **dual-substrate architecture**: a vector substrate
backed by GeoDataFrame for spatial expressiveness, and a raster substrate backed
by NumPy 2D arrays for high-performance vectorised computation. DisSModel is
available through the DisSModel GitHub organisation and on PyPI.

## Statement of Need

Python has become the lingua franca for geospatial data science, supported by
libraries such as GeoPandas and PySAL. However, these tools are designed for
static analysis. Dynamic spatial modeling — simulating how landscapes evolve over
time — has historically required specialised platforms. In Brazil, TerraME
[@Carneiro2013] and Dinamica EGO are the most widely adopted general-purpose
frameworks, while institutions elsewhere often rely on narrower, more specific
allocation models such as CLUE and CLUE-S [@Veldkamp1996]. This fragmentation
leaves researchers choosing between a general-purpose Lua-based toolchain and
single-purpose implementations with no shared contract between them.

While TerraME is conceptually robust, its reliance on Lua scripting — a language
with substantially smaller adoption in the data science ecosystem than Python —
creates a barrier for data scientists, and the framework itself has seen no new
release since August 2020. General-purpose simulation libraries, meanwhile, lack
native synchronisation between a time-stepped clock and the geographical state of
a GeoDataFrame. DisSModel fills this gap with a lightweight, purpose-built
scheduler coupled directly to vector and raster spatial state, providing a
Pythonic, actively maintained implementation of the TerraME paradigm — and,
through its satellite packages, of specific allocation models like CLUE and
CLUE-S as well.

Reproducibility is a first-class concern: the `executor` module provides a
standardised lifecycle — `validate → load → run → save` — that captures
provenance metadata (input checksums, parameters, timing, output paths) in an
`ExperimentRecord` object generated automatically for every run, with no
additional instrumentation by the modeller.

## State of the Field

DisSModel occupies a niche between general-purpose agent-based modeling (ABM)
libraries and specialised GIS simulation software:

| Aspect | TerraME | Dinamica EGO | DisSModel |
|--------|---------|--------------|-----------|
| Language | Lua | Visual/Internal | Python |
| Simulation Engine | Discrete Event | Cellular Automata | Time-stepped scheduler |
| Spatial Structure | CellularSpace (Fixed) | Cellular Grid | GeoDataFrame + NumPy (Dual) |
| GIS Integration | TerraLib | Native Raster | GeoPandas / Rasterio |
| Extensibility | Script-based | Block-based | Class Inheritance |
| Reproducibility | Manual | Manual | Automated (ExperimentRecord) |
| Neighborhoods | GPM Support | Limited | libpysal weights (Queen, Rook, KNN, custom) |

Frameworks like NetLogo and Mesa are excellent for ABM but require boilerplate to
handle real-world spatial projections. DisSModel uses GeoPandas as its core
engine, following the discrete spatial modeling approach proposed by
@SantosJunior2025.

## Software Design

DisSModel is organised into five modules with strict separation of concerns,
extensible through class inheritance. **Core** manages the simulation clock: the
`Environment` class orchestrates time progression, and spatial models auto-register
at instantiation, receiving clock ticks through `setup / pre_execute / execute /
post_execute` hooks. **Geo** provides the dual-substrate design: a vector
substrate (`SpatialModel`, `CellularAutomaton`) on GeoDataFrame with libpysal
neighbourhoods [@Rey2021], and a raster substrate (`RasterModel`,
`RasterCellularAutomaton`) on NumPy arrays with vectorised operations (`shift2d`,
`focal_sum`, `neighbor_contact`) replacing cell-by-cell loops. **Executor** defines
the `ModelExecutor` four-phase lifecycle (`validate`, `load`, `run`, `save`);
subclasses self-register via `__init_subclass__`, and every run produces an
`ExperimentRecord` capturing input checksum, parameters, timing, and output paths.
**IO** provides a unified dataset abstraction (`load_dataset` / `save_dataset`)
across GeoDataFrame, GeoTIFF, and Xarray/Zarr, including transparent `s3://`
resolution. **Visualization** integrates Matplotlib, Streamlit-compatible input
widgets, and `RasterMap` for raster rendering.

This extensibility has already produced independent domain packages:
`dissmodel-ca` [@DisSModelCA] (Cellular Automata patterns), `dissmodel-sysdyn`
[@DisSModelSysDyn] (System Dynamics components), and `DisSLUCC-Continuous`
[@DisSLUCCContinuous], which implements the continuous LUCC modeling components of
LUCCME — Demand, Potential, and Allocation [@Veldkamp1996; @Verburg2004] — on both
substrates and the same `ModelExecutor` contract, an explicit Python counterpart
to TerraME/LUCCME.

## Performance

The vector substrate offers spatial expressiveness; the raster substrate achieves
high throughput via NumPy vectorisation. All benchmarks were run on an Intel Core
i7-7700T CPU @ 2.90GHz, 15 GB RAM (Ubuntu, Python 3.12.3, NumPy 2.4.6, GeoPandas
1.1.3); absolute timings vary by hardware, but the relative speedup pattern is the
result of interest.

**Conway's Game of Life** confirms mathematical equivalence across substrates with
different throughput:

| Grid | Cells | Raster (ms/step) | Vector (ms/step) | Speedup |
|-----:|------:|-----------------:|-----------------:|--------:|
| 10×10 | 100 | 0.12 | 74.81 | 639× |
| 50×50 | 2,500 | 0.19 | 1,707.76 | 8,809× |
| 100×100 | 10,000 | 0.41 | 7,069.14 | 17,394× |
| 200×200 | 40,000 | 1.21 | — | — |
| 500×500 | 250,000 | 9.74 | — | — |
| 1,000×1,000 | 1,000,000 | 30.60 | — | — |

**BR-MANGUE coastal dynamics.** The foundation for coupled mangrove-flood modeling
was established by Bezerra et al. [@Bezerra2013] and extended in @Bezerra2025BM,
co-authored by the submitting author and Felipe Martins Sousa, who now ports
BR-MANGUE to DisSModel. The `brmangue-dissmodel` package [@BRMangue] validates the
raster implementation against TerraME over the Maranhão Island dataset (50,496
cells, 20 steps): land use matches on 99.90% of cells, soil on 99.85%, and
elevation (1 mm tolerance) on 90.67% (MAE 0.0033 m); match percentage is the
appropriate metric for these categorical outputs [@Pontius2008]. Reproducible via
`brmangue-dissmodel/src/brmangue/executors/benchmark_executor.py` against
committed golden references, with `tests/test_model_invariants.py` and
`tests/test_transition_rules.py` covering structural correctness.

Cross-substrate equivalence (60×60 synthetic grid, 3,600 cells, 10 steps) shows
100% match for land use and soil and 100% match for elevation under tolerance
(MAE 0.000959 m, max error 0.024 m), with the raster substrate running at 2.1
ms/step against 84.2 ms/step for vector (40.1× speedup). The residual elevation
divergence reflects floating-point rounding differences, not algorithmic
disagreement. Each run automatically produces an `ExperimentRecord` with timings,
checksums, and artifact paths.

**DisSLUCC-Continuous** implements the continuous CLUE-like allocation algorithm
[@Veldkamp1996]; MAE is the appropriate metric for its fractional outputs
[@Pontius2008; @Willmott2005]. Over the Lab1 study area (6,574 cells, 6 steps),
both substrates reproduce the TerraME/LUCCME reference at MAE = 0.0036 (RMSE
0.0062, max error 0.027) in [0,1] scale, consistent with expected divergence
between independent implementations. Vector and raster are numerically identical
(MAE = 0.000), and the raster substrate is 3.9× faster (44.0 ms/step vs 172.8
ms/step). Reproducible via
`disslucc-continuous/tests/test_benchmark_validation.py`. Full end-to-end
provenance from raw inputs to final metrics is addressed by the
`dissmodel-platform` satellite package.

## Research Impact Statement

DisSModel's scientific lineage is rooted in the TerraME/LuccME research program at
INPE. The submitting author conducted doctoral research at INPE under Prof.
Gilberto Câmara and Dr. Ana Paula Dutra Aguiar — principal architects of
TerraME/LuccME — and has co-authored LuccME since 2009. On 7 May 2026, DisSModel
was presented at INPE's Graduate Program in Applied Computing seminar series
(recording: https://youtu.be/o7pMJt0CvXU), connecting the framework to the
institutional community that maintains TerraME and LuccME.

The framework is in active use across two UFMA research groups. Within LambdaGeo,
graduate students develop `disslucc-continuous` and `brmangue-dissmodel` as part
of their Master's research. Independently, Prof. Denilson da Silva Bezerra (UFMA,
former INPE researcher), whose doctoral work established BR-MANGUE's scientific
foundation [@Bezerra2013], actively uses the DisSModel reimplementation in his own
coastal dynamics research program (PVCBS4959-2025, PVCBS4960-2025;
https://sigaa.ufma.br/sigaa/public/docente/pesquisa.jsf?siape=3104707), a
collaboration predating DisSModel itself [@Bezerra2025BM].

Starting August 2026, the project receives its first PIBIC-funded undergraduate
research fellows (CNPq), under approved institutional project PVCET5136-2026 at
UFMA. The concentrated 2026 development effort was deliberately oriented toward
this milestone: stabilizing the `ModelExecutor` contract so each fellow can own an
independent repository — `disslucc-continuous`, `disslucc-discrete`,
`brmangue-dissmodel`, or `disscube` — without core changes.

Since the original submission, development has continued with `disslucc-discrete`
[@DisSLUCCDiscrete], a CLUE-S-like discrete allocation package using logistic
regression — the discrete counterpart to `DisSLUCC-Continuous`. An initial version
has been validated against the Lab6 case study (Moju municipality, 5,914 cells, 6
steps) from the original TerraME/LuccME repository, achieving 100% categorical
agreement with the TerraME reference (kappa = 1.0, F1 = 1.0) at 56.8 ms/step.

These independent domain packages — `dissmodel-ca`, `dissmodel-sysdyn`,
`DisSLUCC-Continuous`, `disslucc-discrete`, and `brmangue-dissmodel` — demonstrate
that the `ModelExecutor` contract generalizes across modeling paradigms without
core modifications. Studies such as @Bezerra2022, developed using LuccME,
represent the class of models the DisSLUCC packages are designed to reproduce. A
roadmap toward DisSModel 1.0 (May 2027) anchors a community outreach effort
including an open textbook, *Geospatial Modeling with Python*
(https://lambdageo.github.io/geospatial-modeling-python/), already in progress.
This positions DisSModel as the simulation layer in the Brazilian Earth
Observation stack, complementary to SITS [@Simoes2021] and the Brazil Data Cube
[@Ferreira2020].

## Author Contributions

CRediT roles: **S.S.C.** — Conceptualization, Software (Core, Geo, Executor, IO,
Visualization), Methodology, Validation, Writing, Supervision, Project
administration. **N.J.S.J.** — Conceptualization, Software (initial design),
Validation, Writing (undergraduate thesis [@SantosJunior2025]). **D.S.B.** —
Conceptualization (domain science), Validation, Resources
[@Bezerra2013; @Bezerra2025BM]. **F.M.S.** — Software (`brmangue-dissmodel`), Data
curation, Validation [@Bezerra2025BM]. **J.M.P.A.** — Software
(`disslucc-continuous`), Validation. All authors reviewed and approved the final
manuscript.

## AI Usage Disclosure

Development followed several phases. The initial prototype (May–June 2025),
corresponding to the second author's undergraduate thesis [@SantosJunior2025], did
not involve generative AI. Development resumed in February–March 2026 with Claude
(chat) used mainly for documentation; from April 2026, Gemini CLI accelerated code
generation and refactoring; from June 2026, Claude Code (CLI) was used on newer
satellite repositories such as `disslucc-discrete`. AI tools also assisted with
writing in English, which is not the submitting author's native language. The
scientific design — the TerraME compatibility contract, executor pattern,
dual-substrate architecture, and validation methodology — predates and is
independent of this AI-assisted phase, tracing to the submitting author's
doctoral research at INPE and the undergraduate thesis cited above. AI tools
assisted with implementation velocity and language clarity, not scientific or
architectural decisions. All outputs were reviewed and validated by the human
authors.

## References