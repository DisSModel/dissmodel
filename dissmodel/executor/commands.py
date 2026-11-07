"""
``dissmodel`` command: verify, compare and reproduce experiment records.

    dissmodel verify    run.record.json
    dissmodel compare   A B [--atol 1e-9]       (record .json files or rasters)
    dissmodel reproduce run.record.json [--module pkg.executor] [--atol X]

Exit status is 0 when the outcome is ``identical``, ``values_identical`` or
``equivalent`` and 1 otherwise, so the commands can gate a Makefile or CI job.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pkgutil
import sys
from pathlib import Path

from dissmodel.executor.compare import OK_VERDICTS, compare_files, compare_outputs, summary
from dissmodel.executor.schemas import ExperimentRecord


def load_record(path: str) -> ExperimentRecord:
    return ExperimentRecord.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _output_of(arg: str) -> tuple[str, str | None]:
    """(raster/file path, known sha256) for a record JSON or a plain file."""
    if arg.lower().endswith(".json"):
        rec = load_record(arg)
        if not rec.output_path:
            raise SystemExit(f"{arg}: the record has no output_path")
        return rec.output_path, rec.output_sha256
    return arg, None


# ── verify ────────────────────────────────────────────────────────────────────

def _cmd_verify(args) -> int:
    from dissmodel.io._utils import sha256_file

    record = load_record(args.record)
    if not record.output_path or not record.output_sha256:
        print("✗ the record has no output_path / artifacts['output']")
        return 1
    actual = sha256_file(record.output_path)
    if actual == record.output_sha256:
        print(f"✓ {record.output_path} matches the record ({actual[:16]}…)")
        return 0
    print(f"✗ {record.output_path} does not match the record\n"
          f"    record: {record.output_sha256}\n    file:   {actual}")
    return 1


# ── compare ───────────────────────────────────────────────────────────────────

def _cmd_compare(args) -> int:
    pa, ha = _output_of(args.a)
    pb, hb = _output_of(args.b)
    result = compare_files(pa, pb, args.atol, bytes_a=ha, bytes_b=hb)
    result["of"] = Path(pa).name
    print(summary(result))
    if args.json:
        print(json.dumps(result, indent=2))
    return 0 if result["verdict"] in OK_VERDICTS else 1


# ── reproduce ─────────────────────────────────────────────────────────────────

def _import_executor_module(name: str) -> None:
    """Import ``name``; for a package, import its direct submodules too, because
    an executor registers itself when its module is imported."""
    module = importlib.import_module(name)
    for info in pkgutil.iter_modules(getattr(module, "__path__", [])):
        importlib.import_module(f"{name}.{info.name}")


def _executor_module(original: ExperimentRecord, override: str | None) -> str | None:
    if override:
        return override
    declared = original.resolved_spec.get("model", {}).get("executor_module")
    if declared:
        return declared
    env_exec = (original.metrics.get("environment") or {}).get("executor")
    # "pkg.module.Class" -> "pkg.module": the module that defines the executor.
    return env_exec.rsplit(".", 1)[0] if env_exec and "." in env_exec else None


def reproduce(original: ExperimentRecord, module: str | None = None,
              output: str | None = None, atol: float | None = None):
    """Re-run ``original`` from its stored snapshot; returns (record, comparison)."""
    from dissmodel.executor.cli import _dissmodel_version, _ensure_local_output_dir
    from dissmodel.executor.registry import ExecutorRegistry
    from dissmodel.executor.runner import execute_lifecycle

    name = _executor_module(original, module)
    if name and name != "__main__":
        # Like `python -m`, look for the module in the current folder too.
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        try:
            _import_executor_module(name)
        except ModuleNotFoundError as exc:
            raise SystemExit(
                f"Cannot import the executor module '{name}' ({exc}).\n"
                "Run the command from the folder that contains it, or give "
                "its name with --module."
            ) from exc
    try:
        executor_cls = ExecutorRegistry.get(original.model_name)
    except KeyError:
        raise SystemExit(
            f"Executor '{original.model_name}' is not registered. The record was made "
            "by a script, so say where the executor is defined:\n"
            "    dissmodel reproduce <record.json> --module <module that defines it>"
        ) from None

    record = ExperimentRecord(
        model_name=original.model_name, model_commit=original.model_commit,
        code_version=_dissmodel_version(), resolved_spec=original.resolved_spec,
        input_format=original.input_format, column_map=original.column_map,
        band_map=original.band_map, parameters=original.parameters,
        period=original.period, source=original.source.model_copy(),
    )
    out = Path(output) if output else Path(original.output_path or "output.tif")
    record.output_path = str(out.with_name(f"{out.stem}.repro{out.suffix}")) \
        if not output else str(out)
    _ensure_local_output_dir(record.output_path)
    record.metrics["reproduces"] = original.experiment_id

    record, _ = execute_lifecycle(executor_cls(), record)
    result = compare_outputs(original, record, atol)
    record.metrics["reproduction"] = result
    record.add_log(summary(result))
    return record, result


def _cmd_reproduce(args) -> int:
    from dissmodel.executor.cli import _record_path, _save_record_locally

    original = load_record(args.record)
    record, result = reproduce(original, args.module, args.output, args.atol)
    _save_record_locally(record, record.output_path)
    print(summary(result))
    print(f"record: {_record_path(record.output_path)}")
    return 0 if result["verdict"] in OK_VERDICTS else 1


# ── entry point ───────────────────────────────────────────────────────────────

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dissmodel", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="check an output file against its record's SHA-256")
    v.add_argument("record")
    v.set_defaults(func=_cmd_verify)

    c = sub.add_parser("compare", help="compare two outputs (rasters or record .json files)")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--atol", type=float, default=None,
                   help="declared absolute tolerance; enables the 'equivalent' verdict")
    c.add_argument("--json", action="store_true", help="also print the full result as JSON")
    c.set_defaults(func=_cmd_compare)

    r = sub.add_parser("reproduce", help="re-run a record and compare with its output")
    r.add_argument("record")
    r.add_argument("--module", default=None,
                   help="module that registers the executor (default: from the record)")
    r.add_argument("--output", "-o", default=None)
    r.add_argument("--atol", type=float, default=None)
    r.set_defaults(func=_cmd_reproduce)
    return p


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
