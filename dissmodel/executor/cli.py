from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    # tomllib entered the stdlib in 3.11; tomli is its backport for 3.10
    import tomli as tomllib


# ── Parameter helpers ─────────────────────────────────────────────────────────

def _parse_params(param_list: list[str] | None) -> dict:
    """Parse KEY=VALUE strings into a typed dict."""
    params: dict[str, int | float | bool | str] = {}
    for item in param_list or []:
        key, _, raw = item.partition("=")
        for cast in (int, float):
            try:
                params[key] = cast(raw)
                break
            except ValueError:
                pass
        else:
            if raw.lower() in ("true", "false"):
                params[key] = raw.lower() == "true"
            else:
                params[key] = raw
    return params


def _load_toml(path: str) -> tuple[dict, dict]:
    """Load parameters and full spec from a TOML file."""
    with open(path, "rb") as f:
        config = tomllib.load(f)
    model  = config.get("model", {})
    params = model.get("parameters", {})
    return params, model


def _load_local_params(toml_path: str | None = None) -> tuple[dict, dict]:
    """
    Load parameters and full spec from a TOML file.
    Uses --toml if provided, otherwise falls back to model.toml in current dir.
    Returns (parameters, full_model_spec).
    """
    if toml_path:
        if not Path(toml_path).exists():
            print(f"TOML file not found: {toml_path}", file=sys.stderr)
            sys.exit(1)
        return _load_toml(toml_path)

    path = Path("model.toml")
    if not path.exists():
        return {}, {}
    return _load_toml(str(path))


# ── Record factory ────────────────────────────────────────────────────────────

def _build_record(args):
    from dissmodel.executor.schemas import DataSource, ExperimentRecord

    toml_path    = getattr(args, "toml", None)
    params, spec = _load_local_params(toml_path)
    params       = {**params, **_parse_params(args.param)}   # CLI overrides TOML

    # land_use_types lives under spec, not parameters
    if "land_use_types" in spec:
        lu = spec["land_use_types"]
        if isinstance(lu, dict):
            spec["land_use_types"] = lu.get("types", [])

    record = ExperimentRecord(
        model_name    = "local",
        model_commit  = "local-cli",
        code_version  = "dev",
        resolved_spec = {"model": spec} if spec else {},
        source        = DataSource(
            type = "s3" if args.input.startswith("s3://") else "local",
            uri  = args.input,
        ),
        input_format  = getattr(args, "format", "auto"),
        parameters    = params,
        column_map    = _parse_params(getattr(args, "column_map", None)),
        band_map      = _parse_params(getattr(args, "band_map", None)),
    )

    if getattr(args, "output", None):
        record.output_path = args.output

    return record


# ── Output path intelligence (CLI-only) ───────────────────────────────────────

def _apply_output_path_intelligence(record, args) -> None:
    """
    Inject experiment_id into the output path for traceability.

    Must run before execute_lifecycle so that save() receives the
    already-corrected path.

    Scenario A: user passed a directory → generate a safe filename.
    Scenario B: user passed a file without the experiment ID → inject it.
    """
    if not record.output_path:
        return

    p            = Path(record.output_path)
    exp_id_short = record.experiment_id[:8]

    if str(record.output_path).endswith(("/", "\\")) or p.is_dir():
        # Scenario A — directory only, generate filename
        safe_name          = f"simulacao_{exp_id_short}.tif"
        record.output_path = str(p / safe_name)
    elif exp_id_short not in p.name:
        # Scenario B — file path without the experiment ID
        safe_name          = f"{p.stem}_{exp_id_short}{p.suffix}"
        record.output_path = str(p.with_name(safe_name))

    # Keep args.output in sync so the .json and .md artefacts follow
    args.output = record.output_path


# ── Commands ──────────────────────────────────────────────────────────────────

def _cmd_run(executor_cls, args) -> None:
    from dissmodel.executor.runner import execute_lifecycle
    from dissmodel.io._utils       import write_text

    record   = _build_record(args)
    executor = executor_cls()

    # Output path intelligence runs before save() inside execute_lifecycle
    _apply_output_path_intelligence(record, args)

    print("▶ Validating...")
    print("▶ Loading...")
    print("▶ Running...")
    print("▶ Saving...")

    record, timings = execute_lifecycle(executor, record)

    t_val   = timings["time_validate_sec"]
    t_load  = timings["time_load_sec"]
    t_run   = timings["time_run_sec"]
    t_save  = timings["time_save_sec"]
    t_total = timings["time_total_sec"]

    # ── Profiling Markdown artefact ───────────────────────────────────────────
    md_report = (
        f"# Profiling Report: {getattr(executor_cls, 'name', 'Model')}\n\n"
        f"**Experiment ID:** `{record.experiment_id}`\n"
        f"**Date:** `{record.created_at.isoformat()}`\n\n"
        "## Execution Times\n\n"
        "| Phase | Time (seconds) | % of Total |\n"
        "|---|---|---|\n"
        f"| **Validate** | {t_val:.3f}   | {(t_val   / t_total) * 100:.1f}% |\n"
        f"| **Load**     | {t_load:.3f}  | {(t_load  / t_total) * 100:.1f}% |\n"
        f"| **Run**      | {t_run:.3f}   | {(t_run   / t_total) * 100:.1f}% |\n"
        f"| **Save**     | {t_save:.3f}  | {(t_save  / t_total) * 100:.1f}% |\n"
        f"| **Total**    | **{t_total:.3f}** | **100%** |\n"
    )

    if record.output_path:
        base_dir = str(Path(record.output_path).parent)
    elif args.output:
        base_dir = str(Path(args.output).parent)
    else:
        base_dir = "."

    profiling_uri = f"{base_dir}/profiling_{record.experiment_id[:8]}.md"

    try:
        chk = write_text(md_report, profiling_uri, content_type="text/markdown")
        record.add_artifact("profiling", chk)
        record.add_log(f"Saved profiling artifact → {profiling_uri}")
    except Exception as e:
        record.add_log(f"Warning: Could not save profiling artifact: {e}")

    # ── Final JSON record and summary prints ──────────────────────────────────
    _save_record_locally(record, args.output)

    print(f"\n✅ Completed")
    print(f"   output:  {record.output_path}")
    print(f"   record:  {_record_path(args.output)}")

    if record.artifacts:
        print("   artifacts:")
        for art_name, art_chk in record.artifacts.items():
            print(f"      - {art_name}: {art_chk[:16]}...")

    print(f"   status:  {record.status}")
    print(
        f"   ⏱️  Times: val={t_val:.2f}s | load={t_load:.2f}s | "
        f"run={t_run:.2f}s | save={t_save:.2f}s | TOTAL={t_total:.2f}s"
    )

    for log in record.logs:
        print(f"   {log}")


def _cmd_validate(executor_cls, args) -> None:
    from dissmodel.executor.testing import ExecutorTestHarness

    harness = ExecutorTestHarness(executor_cls)
    ok      = harness.run_contract_tests()

    if getattr(args, "input", None):
        record = _build_record(args)
        harness.run_with_sample_data(record)

    sys.exit(0 if ok else 1)


def _cmd_show(executor_cls, args) -> None:
    toml_path    = getattr(args, "toml", None)
    params, spec = _load_local_params(toml_path)
    params       = {**params, **_parse_params(getattr(args, "param", None))}

    print(f"Executor: {executor_cls.__module__}.{executor_cls.__name__}")
    if hasattr(executor_cls, "name"):
        print(f"Name:     {executor_cls.name}")

    print(f"\nResolved parameters (model.toml + CLI overrides):")
    if params:
        for k, v in params.items():
            print(f"  {k} = {v!r}")
    else:
        print("  (none — no model.toml found and no --param given)")

    if spec:
        print(f"\nSpec sections: {list(spec.keys())}")


# ── Parser ────────────────────────────────────────────────────────────────────

def _add_common_args(p) -> None:
    """Add arguments shared across all subcommands."""
    p.add_argument(
        "--toml", "-t", default=None, metavar="FILE",
        help="TOML spec file (default: model.toml in current directory)",
    )
    p.add_argument(
        "--param", "-p", action="append", metavar="KEY=VALUE",
        help="Override model parameter (repeatable)",
    )


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        description="DisSModel CLI — run and validate executors locally",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ──────────────────────────────────────────────────────────────────
    run_p = sub.add_parser("run", help="Run the simulation locally")
    _add_common_args(run_p)
    run_p.add_argument("--input",  "-i", required=True,
                       help="Input URI: local path or s3://bucket/key")
    run_p.add_argument("--output", "-o", default=None,
                       help="Output path: local file or s3://bucket/key")
    run_p.add_argument("--column-map", action="append", metavar="CANONICAL=REAL",
                       help="Column mapping for vector input (repeatable)")
    run_p.add_argument("--band-map",   action="append", metavar="CANONICAL=REAL",
                       help="Band mapping for raster input (repeatable)")
    run_p.add_argument("--format", choices=["vector", "raster", "auto"],
                       default="auto")
    run_p.set_defaults(func=_cmd_run)

    # ── validate ─────────────────────────────────────────────────────────────
    val_p = sub.add_parser("validate", help="Validate executor contract without running")
    _add_common_args(val_p)
    val_p.add_argument("--input", "-i", default=None,
                       help="Optional input for full cycle test")
    val_p.set_defaults(func=_cmd_validate)

    # ── show ─────────────────────────────────────────────────────────────────
    show_p = sub.add_parser("show", help="Show resolved parameters")
    _add_common_args(show_p)
    show_p.set_defaults(func=_cmd_show)

    return parser


# ── Public entry point ────────────────────────────────────────────────────────

def run_cli(executor_cls, args=None) -> None:
    """
    Entry point for running an executor from the command line.
    Called directly by the researcher's executor module.

    Usage
    -----
    if __name__ == "__main__":
        from dissmodel.executor.cli import run_cli
        run_cli(MyExecutor)

    Terminal:
        python -m my_package.my_executor run --input data/grid.zip
        python -m my_package.my_executor run --toml configs/model.toml --input data/grid.zip
        python -m my_package.my_executor validate
        python -m my_package.my_executor show --toml configs/model.toml
    """
    parser = _build_parser()
    parsed = parser.parse_args(args)
    parsed.func(executor_cls, parsed)


def _record_path(output_path: str | None) -> str:
    """Derive record path from output path."""
    if not output_path:
        return "experiment_record.json"
    p = Path(output_path)
    return str(p.with_name(p.stem + ".record.json"))


def _save_record_locally(record, output_path: str | None) -> None:
    """Save ExperimentRecord JSON next to the output file."""
    path = Path(_record_path(output_path))
    path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
