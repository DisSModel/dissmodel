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
  - name: Denilson da Silva Bezerra
    affiliation: "1"
    orcid: 0000-0002-9567-7828

affiliations:
  - name: Universidade Federal do Maranhão (UFMA)
    index: "1"
    city: São Luís
    state: MA
    country: Brazil
date: 24 September 2026
bibliography: paper.bib
---

## Summary

DisSModel (Discrete Spatial Modeling) is a modular Python framework for spatially
explicit dynamic modeling, targeting the complexities of Land Use and Land Cover
Change (LUCC). It translates the modeling paradigms of the TerraME framework
[@Carneiro2013] into the Python ecosystem, enabling researchers to simulate
complex socio-environmental systems — forest fires, epidemiological spreads,
coastal dynamics — by coupling a time-stepped clock with the spatial data
structures of GeoPandas [@Jordahl2021].

The framework provides a **dual-substrate architecture**: a vector substrate
backed by GeoDataFrame for spatial expressiveness, and a raster substrate backed
by NumPy 2D arrays for high-performance vectorised computation. DisSModel is
available through the DisSModel GitHub organisation and on PyPI.

## Statement of Need

Python has become the lingua franca for geospatial data science, supported by
libraries such as GeoPandas and PySAL — but these tools target static analysis.
Dynamic spatial modeling, simulating how landscapes evolve over time, has
historically required specialised platforms. In Brazil, TerraME [@Carneiro2013] and
Dinamica EGO [@SoaresFilho2002; @SoaresFilho2013] are the most widely adopted general-purpose frameworks, while
institutions elsewhere rely on narrower allocation models such as CLUE and CLUE-S
[@Veldkamp1996; @Verburg2002]. This fragmentation leaves researchers choosing between a Lua-based
toolchain and single-purpose implementations with no shared contract.

While TerraME is conceptually robust, its reliance on Lua — a language with far
smaller adoption in data science than Python — creates a barrier for data
scientists, and the framework has seen no new release since August 2020.
General-purpose simulation libraries, meanwhile, lack native synchronisation
between a time-stepped clock and the geographical state of a GeoDataFrame.
DisSModel fills this gap with a lightweight scheduler coupled directly to vector
and raster spatial state, providing a Pythonic, actively maintained implementation
of the TerraME paradigm — and, through its satellite packages, of allocation
models like CLUE and CLUE-S.

Reproducibility is a first-class concern: the `executor` module provides a
standardised lifecycle — `validate → load → run → save` — capturing provenance
metadata (input checksums, parameters, timing, output paths) in an
`ExperimentRecord` generated automatically for every run, with no additional
instrumentation by the modeller.

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

NetLogo [@Wilensky1999] and Mesa [@Kazil2020] are excellent for ABM but require boilerplate to handle
real-world spatial projections. DisSModel uses GeoPandas as its core engine,
following the discrete spatial modeling approach of @SantosJunior2025.

## Software Design

DisSModel is organised into five modules with strict separation of concerns,
extensible through class inheritance. **Core** manages the simulation clock: the
`Environment` orchestrates time progression, and spatial models auto-register at
instantiation, receiving ticks through `setup / pre_execute / execute /
post_execute` hooks. **Geo** provides the dual-substrate design: a vector
substrate (`SpatialModel`, `CellularAutomaton`) on GeoDataFrame with libpysal
neighbourhoods [@Rey2021], and a raster substrate (`RasterModel`,
`RasterCellularAutomaton`) on NumPy arrays with vectorised operations (`shift2d`,
`focal_sum`, `neighbor_contact`) replacing cell-by-cell loops. **Executor** defines
the `ModelExecutor` four-phase lifecycle (`validate`, `load`, `run`, `save`);
subclasses self-register via `__init_subclass__`, and every run produces an
`ExperimentRecord` with input checksum, parameters, timing, and output paths.
**IO** provides a unified dataset abstraction (`load_dataset` / `save_dataset`)
across GeoDataFrame, GeoTIFF, and Xarray/Zarr, with transparent `s3://`
resolution. **Visualization** integrates Matplotlib, Streamlit-compatible widgets,
and `RasterMap`.

This extensibility has already produced independent domain packages:
`dissmodel-ca` [@DisSModelCA] (Cellular Automata patterns), `dissmodel-sysdyn`
[@DisSModelSysDyn] (System Dynamics), and `disslucc` [@DisSLUCC], which
implements LUCCME's continuous and discrete components — Demand, Potential,
and Allocation [@Veldkamp1996; @Verburg2002] — on the raster substrate and
the same `ModelExecutor` contract, an explicit Python counterpart to
TerraME/LuccME.

## Validation and Performance

The vector substrate offers spatial expressiveness; the raster substrate enforces
vectorised rules over NumPy arrays. All benchmarks ran on an Intel Core
i7-7700T @ 2.90GHz, 15 GB RAM (Ubuntu, Python 3.12.3, NumPy 2.4.6, GeoPandas
1.1.3); absolute timings vary by hardware, but the relative speedup is the result
of interest.

**Conway's Game of Life** confirms mathematical equivalence across substrates with
different throughput:

| Grid | Cells | Raster, vectorised rule (ms/step) | Vector, per-cell `rule(idx)` (ms/step) | Speedup |
|-----:|------:|-----------------:|-----------------:|--------:|
| 10×10 | 100 | 0.12 | 74.81 | 639× |
| 50×50 | 2,500 | 0.19 | 1,707.76 | 8,809× |
| 100×100 | 10,000 | 0.41 | 7,069.14 | 17,394× |
| 200×200 | 40,000 | 1.21 | — | — |
| 500×500 | 250,000 | 9.74 | — | — |
| 1,000×1,000 | 1,000,000 | 30.60 | — | — |

The speedup therefore measures a per-cell rule (one Python call per cell) against a
vectorised one, not the substrates themselves; vector runs above 10,000 cells were omitted.

**BR-MANGUE coastal dynamics.** The foundation for coupled mangrove-flood modeling
was established by Bezerra et al. [@Bezerra2013] and extended in @Bezerra2025BM,
whose co-authors include Denilson da Silva Bezerra, Felipe Martins Sousa and the
submitting author — the same researchers responsible for the DisSModel reimplementation. The
`brmangue-dissmodel` package [@BRMangue]
validates the raster implementation against TerraME over the Maranhão Island
dataset (50,496 cells). In the baseline scenario (19 steps) land use and soil match
exactly at every checkpoint, and elevation matches on 97.4% of cells within 1 mm
(MAE 0.00038 m; maximum absolute error 0.10 m against elevations of 1–58 m); match
percentage is the appropriate metric for categorical outputs [@PontiusEtAl2011]. In the
flooding scenario (the laboratory parameters, 2,469 cells flooded by step 11) soil
matches exactly and land use differs in fewer than 0.05% of cells, with elevation within
1 mm on 94.9% of cells after 10 steps. The residual elevation differences are
floating-point rounding in the order of summation, not a difference in the rules. Both
scenarios are reproducible via the package's validation executor.

Cross-substrate equivalence (60×60 synthetic grid, 3,600 cells, 10 steps) shows
100% match for land use, soil, and elevation under tolerance (MAE 0.0011 m, max
error 0.024 m), with raster at 2.0 ms/step against 76.4 ms/step for vector (37.4×
speedup; the vector port follows TerraME's per-cell loops); the residual elevation
divergence is floating-point rounding, not algorithmic disagreement.

**disslucc as a second case.** `disslucc` [@DisSLUCC], a package built on DisSModel,
reimplements the LuccME demand, potential and allocation components (continuous CLUE-like
[@Veldkamp1996] and discrete CLUE-S-like). It is used here to test the `ModelExecutor` contract
and the raster substrate against a second TerraME application, not as a result of its own. Its
checks live in a separate, versioned benchmark [@DisSLUCCBenchmark] that compares every simulated
year, iteration counts included, with per-year outputs generated in a containerised TerraME
[@TerraMEDocker] and checked by SHA-256. Scenarios follow the LuccME test labs (`labNN`); the
`labNN_mdX` variants exercise the convergence loop. MAE suits fractional outputs
[@PontiusEtAl2011; @Willmott2005].

`lab01_md1643` (continuous, 6,574 cells, 6 steps) matches the reference with MAE = 0.0036 in the
final year (mean over years 0.0026, [0,1] scale). The residual is one deliberate deviation:
LuccME's per-cell correction (`correctCellChange`) never executes, because its guard reads a
field name that does not match the one defined, while `disslucc` runs it by default. Without it
(`cell_correction=False`) the match holds in every year, with identical iteration counts
(0, 0, 8, 26, 18, 17, 17; MAE < 1e-7). `lab15_md10` (discrete, 5,914 cells) reproduces the
reference cell for cell, with zero quantity and allocation disagreement [@PontiusMillones2011]
and identical iteration counts (0, 67, 56, 56, 61, 61); the final map alone only checks
coefficient transcription, and the iterations check the convergence loop. Overall, ten of the 21
LuccME test labs and the two variants match with identical iteration counts and differences up to
3e-6 (single-precision paths). A validated lab runs in 0.1 to 0.5 s on the hardware above (median
of five; `make timing`), against 2 to 9 s for one uncontrolled TerraME run: informative, not a
speed ratio.

## Research Impact Statement

DisSModel's scientific lineage is rooted in the TerraME/LuccME research program at
INPE. The submitting author conducted doctoral research at INPE under Prof.
Gilberto Câmara and Dr. Ana Paula Dutra Aguiar — principal architects of
TerraME/LuccME — and has co-authored the modeling program since 2009
[@Moreira2009; @Costa2009]; `disslucc` reimplements in Python the
continuous and discrete allocation components of that lineage [@LuccME]. On
7 May 2026, DisSModel was presented at INPE's Graduate Program in Applied
Computing seminar series (recording: https://youtu.be/o7pMJt0CvXU).

The framework is in active use across two UFMA research groups. Within LambdaGeo,
`brmangue-dissmodel` builds on a Master's student's reference implementation. Independently, Prof. Denilson da Silva Bezerra (UFMA, former
INPE), whose doctoral work established BR-MANGUE's scientific foundation
[@Bezerra2013], uses the DisSModel reimplementation in his own coastal dynamics
program (UFMA projects PVCBS4959-2025 and PVCBS4960-2025), a
collaboration predating DisSModel itself [@Bezerra2025BM].

Since September 2026, four undergraduate research fellows, funded by UFMA and by CNPq,
are being trained on the project. The 2026 development effort prepared for this by stabilizing
the `ModelExecutor` contract, so that each fellow can own an independent repository —
`disslucc`, `brmangue-dissmodel`, or `disscube` [@DisSCube] (a data-cube layer, a Python alternative to
TerraME's `fillCellularSpace`) — without core changes.

Studies such as @Bezerra2022, developed using LuccME, are the class
of models `disslucc` aims to reproduce. A roadmap toward
DisSModel 1.0 (May 2027) anchors community outreach including an open textbook,
*Geospatial Modeling with Python*
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
[@Bezerra2013; @Bezerra2025BM]. **F.M.S.** — Conceptualization, Software (BR-MANGUE
reference implementation), Data curation, Validation [@Bezerra2025BM]. All authors
reviewed and approved the final manuscript.

## Acknowledgements

We thank José Magno Pinheiro Alves for early validation testing.

## AI Usage Disclosure

Development followed several phases. The initial prototype (May–June 2025),
corresponding to the second author's undergraduate thesis [@SantosJunior2025], did
not involve generative AI. Development resumed in February–March 2026 with Claude
(chat) used mainly for documentation; from April 2026, Gemini CLI accelerated code
generation and refactoring; from June 2026, Claude Code (CLI) was used on newer
satellite repositories such as `disslucc`, including the audit of the
validation routines against the original TerraME scripts. In September–October 2026,
in response to the review, Claude (Claude Code and chat) was also used to build the
separate `disslucc-benchmark` repository (scenario definitions, the comparison and
timing scripts, and a differential test against the original Lua code), to reorganize
`disslucc`, and to revise the validation text of this paper so that it matches the
benchmark; the reference results themselves come from the original TerraME/LuccME
code, run unmodified in a container. AI tools also assisted
with writing in English, not the submitting author's native language. The
scientific design — the TerraME compatibility contract, executor pattern,
dual-substrate architecture, and validation methodology — predates and is
independent of this AI-assisted phase, tracing to the submitting author's doctoral
research at INPE and the undergraduate thesis cited above. AI assisted with
implementation velocity and language clarity, not scientific or architectural
decisions. All outputs were reviewed and validated by the authors.

## References
