# CLI

The `dissmodel.executor.cli` module provides the command-line interface for
running and inspecting executors locally. The entry point is `run_cli`,
called directly from the executor module's `__main__` block.

---

## Setting up the CLI

Add this to the bottom of your executor file:

```python
if __name__ == "__main__":
    from dissmodel.executor.cli import run_cli
    run_cli(MyExecutor)
```

This exposes three subcommands: `run`, `validate`, and `show`.

---

## `run` — execute the simulation

```bash
python -m my_package.my_executor run \
    --input  data/grid.zip \
    --output results/

python -m my_package.my_executor run \
    --toml   configs/model.toml \
    --input  data/grid.zip \
    --output results/output.tif

# Override individual parameters
python -m my_package.my_executor run \
    --input data/grid.zip \
    --param end_time=50 \
    --param resolution=100.0
```

After the run, three files are written next to the output:

| File | Content |
|------|---------|
| `output_<id>.tif` | Simulation result |
| `output_<id>.record.json` | Full `ExperimentRecord` (provenance) |
| `profiling_<id>.md` | Per-phase timing table |

The profiling table includes the `Load` phase separately, exposing I/O time
that was previously hidden inside `Run`:

```
| Phase    | Time (s) | % of Total |
|----------|----------|------------|
| Validate | 0.000    | 0.0%       |
| Load     | 2.898    | 49.4%      |
| Run      | 2.972    | 50.6%      |
| Save     | 0.001    | 0.0%       |
| Total    | 5.871    | 100%       |
```

---

## `validate` — check the executor contract

Runs `ExecutorTestHarness` without loading any data. Optionally accepts
`--input` to also run a full cycle test.

```bash
python -m my_package.my_executor validate
python -m my_package.my_executor validate --input data/grid.zip
```

---

## `show` — inspect resolved parameters

Prints the merged parameters from `model.toml` and any `--param` overrides,
without running the simulation.

```bash
python -m my_package.my_executor show
python -m my_package.my_executor show --toml configs/model.toml
```

---

## `model.toml` spec

Parameters can be defined in a `model.toml` file, following the same
convention used to register a model in
[`dissmodel-configs`](https://github.com/DisSModel/dissmodel-configs).
`record.parameters` is built from two layers of the `[model]` table, in
increasing precedence:

1. every `[model]` key that isn't registration metadata
   (`executor_module`, `name`, `class`, `description`, `package`,
   `dissmodel`) or `[model.parameters]` itself — e.g. `land_use_types`,
   a `[[model.potential]]` list, a `[model.static]` table. These are
   simulation input declared once at registration time.
2. `[model.parameters]` — run-specific values, typically ones with no
   sensible default (an input-specific `demand_csv`, a value meant to
   be overridden per run). Wins on overlap with layer 1.

`--param` flags win over both. The full `[model]` table (both layers,
plus the metadata keys) is also kept as-is in
`record.resolved_spec["model"]`, for provenance.

```toml
[model]
class          = "my_model"
package        = "my_package"

# Layer 1 -- merges into record.parameters
land_use_types = ["f", "d", "outros"]

[model.parameters]
# Layer 2 -- merges into record.parameters, wins on overlap with layer 1
end_time   = 20
resolution = 100.0

[[model.potential]]
# Also layer 1 -- list-of-tables sections work the same way
const = 0.74
```

`show` (below) prints `record.parameters` exactly as an executor's
`validate()`/`run()` will see it, so it doubles as a way to check this
merge before running a full simulation.

---

## Output path intelligence

When `--output` is a directory or a file without the experiment ID in its
name, the CLI injects the short experiment ID automatically to prevent
accidental overwrites:

```bash
# Directory → generates filename
--output results/          →  results/simulacao_ec17096d.tif

# File without ID → injects ID
--output results/run.tif   →  results/run_ec17096d.tif

# File already has ID → unchanged
--output results/run_ec17096d.tif  →  unchanged
```

---

## API Reference

::: dissmodel.executor.cli.run_cli
