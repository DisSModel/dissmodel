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
date: 7 October 2026
bibliography: paper.bib
---

## Summary

DisSModel (Discrete Spatial Modeling) is a modular Python framework for spatially explicit dynamic
modeling, targeting Land Use and Land Cover Change (LUCC). It translates the modeling paradigms of
TerraME [@Carneiro2013] into the Python ecosystem, enabling researchers to simulate socio-environmental
systems — forest fires, epidemics, coastal dynamics — by coupling a time-stepped clock with the
spatial data structures of GeoPandas [@Jordahl2021].

Its **dual-substrate architecture** pairs a vector substrate (GeoDataFrame) for spatial expressiveness
with a raster substrate (NumPy 2D arrays) for high-performance vectorized computation. DisSModel is
available through the DisSModel GitHub organization and on PyPI.

## Statement of Need

Python has become the lingua franca for geospatial data science, supported by libraries such as
GeoPandas and PySAL — but these tools target static analysis. Dynamic spatial modeling, simulating
how landscapes evolve over time, has historically required specialized platforms. In Brazil, TerraME
[@Carneiro2013] and Dinamica EGO [@SoaresFilho2002; @SoaresFilho2013] are the most widely adopted
general-purpose frameworks, while narrower allocation models such as CLUE and CLUE-S
[@Veldkamp1996; @Verburg2002] are used elsewhere. Researchers must choose between a Lua-based
toolchain and single-purpose implementations with no shared contract.

TerraME is conceptually robust, but its reliance on Lua — far less common in data science than
Python — is a barrier, and the framework has seen no new release since August 2020. General-purpose
simulation libraries, meanwhile, lack native synchronization between a time-stepped clock and the
state of a GeoDataFrame. DisSModel fills this gap with a lightweight scheduler coupled to vector and
raster spatial state: a Pythonic, actively maintained implementation of the TerraME paradigm and,
through its satellite packages, of allocation models like CLUE and CLUE-S.

Reproducibility is a first-class concern: the `executor` module provides a
standardized lifecycle — `validate → load → run → save` — capturing provenance
metadata (input checksums, parameters, timing, output paths) in an
`ExperimentRecord` generated automatically for every run, with no additional
instrumentation by the modeler.

## State of the Field

DisSModel occupies a niche between general-purpose agent-based modeling (ABM)
libraries and specialized GIS simulation software:

| Aspect | TerraME | Dinamica EGO | DisSModel |
|--------|---------|--------------|-----------|
| Language | Lua | Visual/Internal | Python |
| Simulation Engine | Discrete Event | Cellular Automata | Time-stepped scheduler |
| Spatial Structure | CellularSpace (Fixed) | Cellular Grid | GeoDataFrame + NumPy (Dual) |
| GIS Integration | TerraLib | Native Raster | GeoPandas / Rasterio |
| Extensibility | Script-based | Block-based | Class Inheritance |
| Reproducibility | Manual | Manual | Automated (ExperimentRecord) |

NetLogo [@Wilensky1999] and Mesa [@Kazil2020] are excellent for ABM; Mesa-Geo [@Wang2022] adds GIS
data to Mesa, whereas DisSModel centers on cellular-space state with a synchronized clock and a
reproducible executor lifecycle. DisSModel builds on GeoPandas, following the discrete spatial modeling approach of @SantosJunior2025.

## Software Design

DisSModel is organized into five modules with strict separation of concerns, extensible through
class inheritance. **Core** manages the simulation clock: the `Environment` orchestrates time, and
spatial models auto-register at instantiation, receiving ticks through `setup / pre_execute /
execute / post_execute` hooks. **Geo** provides the dual-substrate design: a vector substrate
(`SpatialModel`, `CellularAutomaton`) on GeoDataFrame with libpysal neighborhoods [@Rey2021], and a
raster substrate (`RasterModel`, `RasterCellularAutomaton`) on NumPy arrays with vectorized
operations (`shift2d`, `focal_sum`, `neighbor_contact`) replacing cell-by-cell loops. **Executor**
defines the `ModelExecutor` four-phase lifecycle (`validate`, `load`, `run`, `save`); subclasses
self-register, and every run produces an `ExperimentRecord` with input checksum, parameters, timing,
and output paths. **IO** provides a unified dataset abstraction across GeoDataFrame, GeoTIFF, and
Xarray/Zarr, with transparent `s3://` resolution. **Visualization** integrates Matplotlib,
Streamlit-compatible widgets, and `RasterMap`.

This extensibility has produced independent domain packages: `dissmodel-ca` [@DisSModelCA]
(Cellular Automata), `dissmodel-sysdyn` [@DisSModelSysDyn] (System Dynamics), and `disslucc`
[@DisSLUCC], which implements LuccME's continuous and discrete Demand, Potential, and Allocation
components [@Veldkamp1996; @Verburg2002] on the raster substrate and the same `ModelExecutor`
contract, an explicit Python counterpart to TerraME/LuccME.

## Validation and Performance

All benchmarks ran on an Intel Core i7-7700T @ 2.90GHz, 15 GB RAM (Ubuntu, Python 3.12.3,
NumPy 2.4.6, GeoPandas 1.1.3); absolute timings vary by hardware.

**Conway's Game of Life** confirms equivalence across substrates: at 100×100 cells the vectorized
raster rule takes 0.41 ms/step against 7,069 ms/step for a per-cell vector rule, and the raster
scales to 10⁶ cells at 30.6 ms/step (per-cell versus vectorized rule).

**BR-MANGUE coastal dynamics.** The coupled mangrove–flood model was established by
Bezerra et al. [@Bezerra2013] and extended in @Bezerra2025BM, co-authored by D.S.B., F.M.S. and the
submitting author, who are also responsible for the DisSModel reimplementation.
`brmangue-dissmodel` [@BRMangue] validates the raster implementation against TerraME over the
Maranhão Island dataset (50,496 cells). In the baseline scenario (19 steps) land use and soil match
exactly at every checkpoint and elevation matches on 97.4% of cells within 1 mm (MAE 0.00038 m;
maximum error 0.10 m); match percentage suits categorical outputs
[@PontiusEtAl2011]. In the flooding scenario (laboratory parameters) TerraME floods 2,469 non-sea
cells by step 11 and the Python model 2,467; soil matches exactly, land use differs in 4 cells
(0.008%), and elevation matches on 94.4% of cells (MAE 0.008 m, maximum error 1.0 m). The residuals
come from exact ties in elevation: the flux rule compares accumulated elevations with `<=`, so a
~1e-16 difference in summation order (sequential in TerraME, per direction in NumPy) can flip a
comparison and, near the flooding threshold, a cell's class. They are floating-point effects, not a
difference in the rules. Both are reproducible with its validation executor.

Cross-substrate equivalence (60×60 synthetic grid, 10 steps) gives 100% match for land use, soil
and elevation under tolerance (MAE 0.0011 m, max 0.024 m; floating-point rounding, not algorithmic
disagreement), with raster at 2.0 ms/step against 76.4 ms/step for vector (37.4×; the vector port
follows TerraME's per-cell loops).

**disslucc as a second case.** `disslucc` [@DisSLUCC], built on DisSModel, reimplements the LuccME
demand, potential and allocation components (continuous CLUE-like [@Veldkamp1996] and discrete
CLUE-S-like). It tests the `ModelExecutor` contract and the raster substrate against a second
TerraME application, not as a result in itself. Its checks live in a separate, versioned benchmark
[@DisSLUCCBenchmark] that compares every simulated year, iteration counts included, with per-year
outputs generated in a containerized TerraME [@TerraMEDocker] and checked by SHA-256. Scenarios
follow the LuccME test labs (`labNN`); the `labNN_mdX` variants exercise the convergence loop. MAE
suits fractional outputs [@PontiusEtAl2011; @Willmott2005].

`lab01_md1643` (continuous, 6,574 cells, 2008–2014) matches the reference with MAE = 0.0036 in the
final year ([0,1] scale). The residual is one deliberate deviation: LuccME's per-cell correction
(`correctCellChange`) never executes, because its guard reads a field name that does not match the
one defined, while `disslucc` runs it by default. Without it (`cell_correction=False`) the match
holds in every year, with identical iteration counts (MAE < 1e-7).
`lab15_md10` (discrete, 5,914 cells) reproduces the reference cell for cell, with zero quantity and
allocation disagreement [@PontiusMillones2011] and identical iteration counts. Overall, ten of 21 LuccME test labs and both variants match with identical iteration
counts and differences up to 3e-6 (single precision); a validated lab runs in 0.1 to 0.5 s on
the hardware above (median of five; `make timing`). The other eleven labs need potential and
allocation components not yet implemented; student fellows are developing them, and each lab joins
the benchmark as its components land.

## Research Impact Statement

DisSModel's scientific lineage is rooted in the TerraME/LuccME research program at INPE. The
submitting author conducted doctoral research there under Prof. Gilberto Câmara and Dr. Ana Paula
Dutra Aguiar — principal architects of TerraME/LuccME — and has co-authored the modeling program
since 2009 [@Moreira2009; @Costa2009]; `disslucc` reimplements in Python the continuous and
discrete allocation components of that lineage [@LuccME].

The framework is in use across two UFMA research groups. Within LambdaGeo, `brmangue-dissmodel`
builds on the reference implementation by co-author F.M.S. Independently, Prof. Denilson da Silva
Bezerra (UFMA, former INPE), whose doctoral work founded BR-MANGUE [@Bezerra2013], uses the DisSModel reimplementation in his own coastal dynamics program (UFMA
projects PVCBS4959-2025 and PVCBS4960-2025), a collaboration predating DisSModel itself
[@Bezerra2025BM].

Since September 2026, four undergraduate research fellows (UFMA, CNPq) are being trained on the
project; the stabilized `ModelExecutor` contract lets each own an independent repository —
`disslucc`, `brmangue-dissmodel`, or `disscube` [@DisSCube] (a data-cube layer, a Python alternative
to TerraME's `fillCellularSpace`) — without core changes.

A roadmap toward DisSModel 1.0 (May 2027) includes an open textbook, *Geospatial Modeling with
Python* (https://lambdageo.github.io/geospatial-modeling-python/), already in progress. This
positions DisSModel as a candidate simulation layer in the Brazilian Earth Observation stack,
complementary to SITS [@Simoes2021] and the Brazil Data Cube [@Ferreira2020].

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

Development followed several phases. The initial prototype (May–June 2025), the second author's
undergraduate thesis [@SantosJunior2025], did not involve generative AI. From February 2026 Claude
(chat) was used for documentation, from April Gemini CLI for code generation and refactoring, and
from June Claude Code (CLI) on satellite repositories such as `disslucc`, including auditing its
validation routines against the original TerraME scripts. In
September–October 2026, in response to the review, Claude (Claude Code and chat) wrote and modified
code and text: the `disslucc-benchmark` repository (scenarios, comparison and timing scripts, a
differential test against the original Lua code); the reorganization of `disslucc`; in
`brmangue-dissmodel`, the diagnosis and correction of two discrepancies with TerraME (neighbor
counting at borders; the snapshot shared by the flood and mangrove models) with tests, a headless
driver for regenerating TerraME outputs, and documentation; and the revision of this paper's
validation text. The reference results come from the original TerraME/LuccME code run unmodified in
a container (for BR-MANGUE, unmodified model files with a new headless driver), so they do not
depend on AI-written code. AI also assisted with English writing. The scientific design — TerraME
compatibility contract, executor pattern, dual-substrate architecture, validation methodology —
predates this phase and traces to the submitting author's doctoral research at INPE. The authors
made the design decisions and chose the validation criteria; AI-generated code and text were
reviewed, tested, and run by the authors.

## References
