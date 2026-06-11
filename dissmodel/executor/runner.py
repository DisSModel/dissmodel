from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dissmodel.executor.model_executor import ModelExecutor
    from dissmodel.executor.schemas import ExperimentRecord


def execute_lifecycle(
    executor: "ModelExecutor",
    record: "ExperimentRecord",
) -> tuple["ExperimentRecord", dict[str, float]]:
    """
    Canonical lifecycle orchestration for DisSModel executors.

    Runs validate → load → run → save in order, times each phase
    independently, and populates record.metrics with the results.

    Used by both the CLI runner and the platform job_runner to ensure
    behavioural parity without code duplication.

    Parameters
    ----------
    executor:
        An instantiated ModelExecutor subclass.
    record:
        The ExperimentRecord for this job. May be mutated in-place by
        load() (e.g. source.checksum) and save() (output_path, status).

    Returns
    -------
    record:
        The completed ExperimentRecord with status, output_path, and
        metrics populated.
    timings:
        Dict with individual phase times and total:
        time_validate_sec, time_load_sec, time_run_sec,
        time_save_sec, time_total_sec.
    """
    t0 = time.perf_counter()
    executor.validate(record)
    t_val = time.perf_counter() - t0

    t0 = time.perf_counter()
    data = executor.load(record)
    t_load = time.perf_counter() - t0

    t0 = time.perf_counter()
    result = executor.run(data, record)
    t_run = time.perf_counter() - t0

    t0 = time.perf_counter()
    record = executor.save(result, record)
    t_save = time.perf_counter() - t0

    t_total = t_val + t_load + t_run + t_save

    timings: dict[str, float] = {
        "time_validate_sec": round(t_val,   3),
        "time_load_sec":     round(t_load,  3),
        "time_run_sec":      round(t_run,   3),
        "time_save_sec":     round(t_save,  3),
        "time_total_sec":    round(t_total, 3),
    }

    record.metrics.update(timings)
    return record, timings
