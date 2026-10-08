# Schemas

The executor schemas are Pydantic models that carry provenance metadata across
the full simulation lifecycle. Every execution produces an `ExperimentRecord`
automatically — no additional instrumentation is required from the modeller.

---

## `ExperimentRecord`

The central provenance object. Created before `execute_lifecycle` is called
and mutated in-place by `load`, `run`, and `save`.

After a completed run, the record contains:

| Field | Populated by | Description |
|-------|-------------|-------------|
| `experiment_id` | automatically | UUID generated at creation |
| `created_at` | automatically | ISO 8601 timestamp |
| `source.checksum` | `load()` | SHA-256 of the input dataset |
| `parameters` | CLI / API | Resolved model parameters |
| `output_path` | `save()` | URI of the output file |
| `output_sha256` | `save()` | SHA-256 of the output file |
| `metrics` | `execute_lifecycle` | Per-phase timing + model-specific metrics |
| `artifacts` | `save()` | Named checksums of extra artefacts |
| `logs` | any phase | Free-form execution log |
| `status` | `save()` | `"completed"` or `"failed"` |

### Example — reading a saved record

```python
from dissmodel.executor.schemas import ExperimentRecord
from pathlib import Path

record = ExperimentRecord.model_validate_json(
    Path("output.record.json").read_text()
)

print(record.experiment_id)
print(record.metrics["time_load_sec"])
print(record.source.checksum)
```

### Example — building a record manually (tests / scripts)

```python
from dissmodel.executor.schemas import ExperimentRecord, DataSource

record = ExperimentRecord(
    model_name   = "my_model",
    model_commit = "abc123",
    code_version = "0.4.0",
    source       = DataSource(type="local", uri="data/input.gpkg"),
    parameters   = {"end_time": 20, "resolution": 100.0},
)
```

---

## `DataSource`

Describes the input dataset. The `checksum` field is filled by `load()`
after the file is read — not before.

```python
DataSource(
    type     = "s3",           # "local" | "s3" | "http"
    uri      = "s3://bucket/input.tif",
    checksum = "",             # filled by load()
)
```

---

## `JobRequest`

Used by the platform API to submit a simulation job. The platform resolves
the executor from `model.class`, installs the package from `model.package`,
and builds the `ExperimentRecord` before dispatching to the worker queue.

```python
from dissmodel.executor.schemas import JobRequest

job = JobRequest(
    model = {
        "class":   "brmangue_raster",
        "package": "git+https://github.com/DisSModel/brmangue-dissmodel@v0.5.0",
        "parameters": {"end_time": 88},
    },
    source = {"type": "s3", "uri": "s3://dissmodel-inputs/grid.zip"},
)
```

---

## API Reference

::: dissmodel.executor.schemas.ExperimentRecord

::: dissmodel.executor.schemas.DataSource

::: dissmodel.executor.schemas.JobRequest
