"""Environment, comparison ladder and the `dissmodel` command (0.7.0)."""
from __future__ import annotations

import json

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from dissmodel.executor import commands
from dissmodel.executor.compare import compare_files, compare_outputs, summary
from dissmodel.executor.environment import environment
from dissmodel.executor.model_executor import ModelExecutor
from dissmodel.executor.runner import execute_lifecycle
from dissmodel.executor.schemas import DataSource, ExperimentRecord
from dissmodel.io._utils import sha256_file, write_bytes


def write_tif(path, array, compress="deflate"):
    profile = dict(driver="GTiff", height=array.shape[0], width=array.shape[1],
                   count=1, dtype=array.dtype, compress=compress)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array, 1)
    return str(path)


@pytest.fixture
def grid():
    return np.arange(100, dtype="float32").reshape(10, 10)


# ── environment ───────────────────────────────────────────────────────────────

def test_environment_has_all_keys_even_without_libraries():
    env = environment(None)
    assert set(env) == {"python", "platform", "machine", "executor",
                        "executor_package", "native", "packages"}
    assert set(env["native"]) == {"gdal", "geos", "proj"}
    assert env["native"]["gdal"] == rasterio.__gdal_version__


# ── comparison ladder ─────────────────────────────────────────────────────────

def test_identical(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    b = write_tif(tmp_path / "b.tif", grid)
    r = compare_files(a, b)
    assert r["verdict"] == "identical"
    assert r["file_identical"] is True and r["values_identical"] is True


def test_same_values_different_bytes(tmp_path, grid):
    """The Mac M3 case: values equal, encoding (compression) differs."""
    a = write_tif(tmp_path / "a.tif", grid, compress="deflate")
    b = write_tif(tmp_path / "b.tif", grid, compress="lzw")
    assert sha256_file(a) != sha256_file(b)
    r = compare_files(a, b)
    assert r["verdict"] == "values_identical"
    assert r["levels"] == {"bytes": False, "values": True, "georef": True, "tolerance": None}


def test_tiny_difference_differs_without_tolerance(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    other = grid.copy()
    other[0, 0] += np.float32(1e-3)
    b = write_tif(tmp_path / "b.tif", other)
    r = compare_files(a, b)
    assert r["verdict"] == "differs"
    assert r["levels"]["tolerance"] is None   # never inferred


def test_tolerance_must_be_declared_and_respected(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    other = grid.copy()
    other[0, 0] += np.float32(1e-3)
    b = write_tif(tmp_path / "b.tif", other)
    assert compare_files(a, b, atol=1e-2)["verdict"] == "equivalent"
    tight = compare_files(a, b, atol=1e-6)
    assert tight["verdict"] == "differs"
    assert tight["max_abs_diff"] == pytest.approx(1e-3, rel=1e-2)


def test_shape_mismatch_is_differs_even_with_tolerance(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    b = write_tif(tmp_path / "b.tif", grid[:5])
    assert compare_files(a, b, atol=1.0)["verdict"] == "differs"


def test_non_raster_stops_at_bytes(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("x"); b.write_text("x")
    r = compare_files(str(a), str(b))
    assert r["verdict"] == "identical" and r["values_identical"] is None
    b.write_text("y")
    assert compare_files(str(a), str(b))["verdict"] == "differs"


def test_summary_mentions_verdict_and_tolerance(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    r = compare_files(a, a, atol=1e-9)
    assert "identical" in summary(r)


# ── lifecycle hooks ───────────────────────────────────────────────────────────

class _Mini(ModelExecutor):
    name = "_test_070_mini"
    def load(self, record): return None
    def run(self, data, record): return None
    def save(self, result, record):
        record.status = "completed"
        return record


def test_lifecycle_records_environment_and_peak_rss():
    rec, _ = execute_lifecycle(_Mini(), ExperimentRecord(model_name="m"))
    assert "environment" in rec.metrics
    assert rec.metrics["environment"]["executor"].endswith("._Mini")
    assert rec.metrics.get("peak_rss_mb", 1) > 0


def test_lifecycle_keeps_environment_set_by_caller():
    rec = ExperimentRecord(model_name="m")
    rec.metrics["environment"] = {"python": "custom"}
    rec, _ = execute_lifecycle(_Mini(), rec)
    assert rec.metrics["environment"] == {"python": "custom"}


def test_progress_lines_are_logged(caplog):
    with caplog.at_level("INFO", logger="dissmodel.executor"):
        execute_lifecycle(_Mini(), ExperimentRecord(model_name="m"))
    phases = [r.message for r in caplog.records if r.message.startswith("[progress]")]
    assert phases[:4] == [f"[progress] phase={p}" for p in ("validate", "load", "run", "save")]


# ── commands, end to end ──────────────────────────────────────────────────────

class _Doubler(ModelExecutor):
    """Reads a GeoTIFF, writes value*2; DETERMINISTIC unless env var asks otherwise."""
    name = "_test_070_doubler"
    compress = "deflate"

    def load(self, record):
        with rasterio.open(record.source.uri) as src:
            return src.read(1), src.profile

    def run(self, data, record):
        arr, profile = data
        return arr * 2, profile

    def save(self, result, record):
        arr, profile = result
        profile.update(compress=type(self).compress)
        import io
        buf = io.BytesIO()
        with rasterio.io.MemoryFile() as mem:
            with mem.open(**profile) as dst:
                dst.write(arr, 1)
            buf.write(mem.read())
        record.output_path = record.output_path or "out.tif"
        record.add_artifact("output", write_bytes(buf.getvalue(), record.output_path))
        record.status = "completed"
        return record


def _original(tmp_path, grid):
    src = write_tif(tmp_path / "in.tif", grid)
    rec = ExperimentRecord(model_name=_Doubler.name, source=DataSource(uri=src))
    rec.output_path = str(tmp_path / "out.tif")
    rec, _ = execute_lifecycle(_Doubler(), rec)
    path = tmp_path / "out.record.json"
    path.write_text(rec.model_dump_json(indent=2))
    return rec, str(path)


def test_verify_ok_and_tampered(tmp_path, grid, capsys):
    rec, path = _original(tmp_path, grid)
    assert commands._cmd_verify(type("A", (), {"record": path})) == 0
    with open(rec.output_path, "ab") as f:
        f.write(b"x")
    assert commands._cmd_verify(type("A", (), {"record": path})) == 1


def test_reproduce_identical(tmp_path, grid):
    rec, _ = _original(tmp_path, grid)
    new, result = commands.reproduce(rec, module=None)
    assert result["verdict"] == "identical"
    assert new.metrics["reproduces"] == rec.experiment_id
    assert new.metrics["reproduction"]["verdict"] == "identical"
    assert new.output_path != rec.output_path


def test_reproduce_with_other_gdal_encoding(tmp_path, grid):
    rec, _ = _original(tmp_path, grid)
    _Doubler.compress = "lzw"
    try:
        _, result = commands.reproduce(rec)
    finally:
        _Doubler.compress = "deflate"
    assert result["verdict"] == "values_identical"


def test_main_exit_codes(tmp_path, grid):
    a = write_tif(tmp_path / "a.tif", grid)
    b = write_tif(tmp_path / "b.tif", grid, compress="lzw")
    other = write_tif(tmp_path / "c.tif", grid + 1)
    with pytest.raises(SystemExit) as ok:
        commands.main(["compare", a, b])
    assert ok.value.code == 0
    with pytest.raises(SystemExit) as bad:
        commands.main(["compare", a, other])
    assert bad.value.code == 1


def test_run_profiling_report_survives_zero_total(monkeypatch, tmp_path, grid):
    """Regression: ZeroDivisionError when the total time is 0.0."""
    from dissmodel.executor import cli
    monkeypatch.setattr(
        "dissmodel.executor.runner.execute_lifecycle",
        lambda ex, rec: (setattr(rec, "status", "completed") or rec,
                         {k: 0.0 for k in ("time_validate_sec", "time_load_sec",
                                           "time_run_sec", "time_save_sec", "time_total_sec")}),
    )
    src = write_tif(tmp_path / "in.tif", grid)
    args = cli._build_parser().parse_args(["run", "-i", src, "-o", str(tmp_path / "o.tif")])
    cli._cmd_run(_Doubler, args)   # must not raise


# ── review fixes: georeference, failed fetch, unverifiable ─────────────────────

def _tif(path, array, *, origin=(0, 10), crs="EPSG:4326", nodata=None):
    from rasterio.transform import from_origin
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
                       count=1, dtype=array.dtype, crs=crs, nodata=nodata,
                       transform=from_origin(origin[0], origin[1], 1, 1)) as dst:
        dst.write(array, 1)
    return str(path)


@pytest.mark.parametrize("change", [dict(origin=(500, 10)), dict(crs="EPSG:3857"), dict(nodata=-9999.0)])
def test_same_values_but_moved_raster_is_not_values_identical(tmp_path, grid, change):
    base = _tif(tmp_path / "a.tif", grid)
    other = _tif(tmp_path / "b.tif", grid, **change)
    r = compare_files(base, other, atol=1.0)
    assert r["verdict"] == "differs"
    assert r["levels"]["georef"] is False
    assert r["levels"]["tolerance"] is None      # tolerance never rescues a moved raster


def test_equal_recorded_checksums_need_no_download():
    o, n = ExperimentRecord(model_name="m"), ExperimentRecord(model_name="m")
    for rec in (o, n):
        rec.output_path = "s3://bucket/out.tif"
        rec.add_artifact("output", "abc")

    def boom(uri, workdir):
        raise AssertionError("must not download")
    assert compare_outputs(o, n, local_copy=boom)["verdict"] == "identical"


def test_failed_download_keeps_byte_level_and_is_unverified():
    o, n = ExperimentRecord(model_name="m"), ExperimentRecord(model_name="m")
    for rec, sha in ((o, "abc"), (n, "def")):
        rec.output_path = "s3://bucket/out.tif"
        rec.add_artifact("output", sha)

    def down(uri, workdir):
        raise RuntimeError("minio down")
    r = compare_outputs(o, n, local_copy=down)
    assert r["levels"]["bytes"] is False
    assert r["verdict"] == "unverified" and "minio down" in r["fetch_error"]


def test_unreadable_raster_is_unverified_not_differs(tmp_path, grid):
    good = write_tif(tmp_path / "a.tif", grid)
    bad = tmp_path / "b.tif"
    bad.write_bytes(b"not a tiff")
    r = compare_files(good, str(bad))
    assert r["verdict"] == "unverified" and "values_error" in r


def test_command_exit_code_is_nonzero_for_unverified(tmp_path, grid):
    good = write_tif(tmp_path / "a.tif", grid)
    bad = tmp_path / "b.tif"
    bad.write_bytes(b"not a tiff")
    with pytest.raises(SystemExit) as e:
        commands.main(["compare", good, str(bad)])
    assert e.value.code == 1


# ── `dissmodel reproduce` finds the executor module in the current folder ─────

_MODULE_SRC = """
from dissmodel.executor import ModelExecutor
from dissmodel.io._utils import write_bytes


class CwdExecutor(ModelExecutor):
    name = "_test_070_cwd"
    def load(self, record): return None
    def run(self, data, record): return None
    def save(self, result, record):
        record.add_artifact("output", write_bytes(b"x", record.output_path))
        record.status = "completed"
        return record
"""


def _record_for(name, module_path_executor):
    rec = ExperimentRecord(model_name=name)
    rec.output_path = "original.bin"
    rec.add_artifact("output", __import__("hashlib").sha256(b"x").hexdigest())
    rec.metrics["environment"] = {"executor": module_path_executor}
    return rec


def test_reproduce_imports_module_from_current_folder(tmp_path, monkeypatch):
    (tmp_path / "cwd_executor_mod.py").write_text(_MODULE_SRC)
    monkeypatch.chdir(tmp_path)
    import sys
    saved = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if p not in ("", str(tmp_path))]
        new, result = commands.reproduce(_record_for("_test_070_cwd", "cwd_executor_mod.CwdExecutor"))
    finally:
        sys.path[:] = saved
        sys.modules.pop("cwd_executor_mod", None)
    assert new.status == "completed" and result["verdict"] == "identical"


def test_reproduce_script_record_without_module_explains_what_to_do():
    rec = _record_for("_test_070_not_registered", "__main__.SomeExecutor")
    with pytest.raises(SystemExit) as e:
        commands.reproduce(rec)
    assert "--module" in str(e.value) and "not registered" in str(e.value)


def test_reproduce_unknown_module_is_a_clear_error():
    rec = _record_for("_test_070_x", "pkg_that_does_not_exist.Exec")
    with pytest.raises(SystemExit) as e:
        commands.reproduce(rec, module="pkg_that_does_not_exist")
    assert "Cannot import the executor module" in str(e.value)


def test_environment_resolves_module_of_python_dash_m_run(monkeypatch):
    import sys
    import types
    from dissmodel.executor.environment import executor_module_name

    class Fake:
        __module__ = "__main__"
        __qualname__ = "Fake"

    fake_main = types.SimpleNamespace(__spec__=types.SimpleNamespace(name="pkg.executors.thing"))
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    assert executor_module_name(Fake) == "pkg.executors.thing"
    assert environment(Fake)["executor"] == "pkg.executors.thing.Fake"

    monkeypatch.setitem(sys.modules, "__main__", types.SimpleNamespace(__spec__=None))
    assert executor_module_name(Fake) == "__main__"      # plain script: stays unknown


def test_reproduce_imports_direct_submodules_of_a_package(tmp_path, monkeypatch):
    pkg = tmp_path / "pkg_executors_070"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")              # does not import its submodules
    (pkg / "thing.py").write_text(_MODULE_SRC.replace("_test_070_cwd", "_test_070_pkg"))
    monkeypatch.chdir(tmp_path)
    import sys
    try:
        rec = _record_for("_test_070_pkg", "somewhere.else.Class")
        rec.resolved_spec = {"model": {"executor_module": "pkg_executors_070"}}
        new, result = commands.reproduce(rec)
    finally:
        for m in [m for m in sys.modules if m.startswith("pkg_executors_070")]:
            sys.modules.pop(m)
        sys.path[:] = [p for p in sys.path if p != str(tmp_path)]
    assert new.status == "completed"
