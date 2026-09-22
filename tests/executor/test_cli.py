from __future__ import annotations

from pathlib import Path
from types  import SimpleNamespace

import pytest

from dissmodel.executor.cli import _build_record, _load_toml, _parse_params, _apply_output_path_intelligence


# ── _parse_params ─────────────────────────────────────────────────────────────

class TestParseParams:

    def test_empty_input_returns_empty_dict(self):
        assert _parse_params(None) == {}
        assert _parse_params([])   == {}

    def test_integer_values_are_cast(self):
        result = _parse_params(["steps=10", "start=0"])
        assert result["steps"] == 10
        assert result["start"] == 0
        assert isinstance(result["steps"], int)

    def test_float_values_are_cast(self):
        result = _parse_params(["rate=0.5", "threshold=1.0"])
        assert result["rate"] == 0.5
        assert isinstance(result["rate"], float)

    def test_integer_takes_precedence_over_float(self):
        """'10' should become int 10, not float 10.0."""
        result = _parse_params(["n=10"])
        assert isinstance(result["n"], int)

    def test_boolean_true_is_cast(self):
        result = _parse_params(["interactive=true", "verbose=True"])
        assert result["interactive"] is True
        assert result["verbose"] is True

    def test_boolean_false_is_cast(self):
        result = _parse_params(["interactive=false", "debug=False"])
        assert result["interactive"] is False
        assert result["debug"] is False

    def test_plain_string_stays_as_string(self):
        result = _parse_params(["crs=EPSG:4326", "label=test"])
        assert result["crs"] == "EPSG:4326"
        assert result["label"] == "test"

    def test_multiple_equals_signs_partition_on_first(self):
        """KEY=a=b should map key → 'a=b'."""
        result = _parse_params(["uri=s3://bucket/key=value"])
        assert result["uri"] == "s3://bucket/key=value"

    def test_duplicate_keys_last_wins(self):
        result = _parse_params(["rate=0.1", "rate=0.9"])
        assert result["rate"] == 0.9


# ── _load_toml ───────────────────────────────────────────────────────────────
#
# Regression coverage for the gap where a model.toml following the
# dissmodel-configs registration convention (spec fields declared at the
# [model] level, not nested under [model.parameters]) silently produced an
# incomplete record.parameters: [model] keys other than [model.parameters]
# were stored in `spec`/resolved_spec only and never reached `params`, even
# though ModelExecutor.run() documents that executors "receive record with
# resolved_spec and parameters already merged". Any executor reading a
# model-level key (land_use_types, a [[model.potential]] list, ...) directly
# from record.parameters -- the natural place for simulation input -- would
# then fail validate() with a "missing parameter" error the file appeared to
# already answer. See disslucc's LuccContinuousExecutor/LuccDiscreteExecutor
# (github.com/DisSModel/disslucc) for a real-world executor with exactly
# that shape, and disslucc's docs/decisions.md for how this was found.

class TestLoadToml:

    def _write(self, tmp_path: Path, content: str) -> str:
        path = tmp_path / "model.toml"
        path.write_text(content)
        return str(path)

    def test_model_level_keys_merge_into_params(self, tmp_path):
        """A [model]-level key outside [model.parameters] (the
        dissmodel-configs registration convention) must reach `params`,
        not just `spec` -- this is the core bug being fixed."""
        toml_path = self._write(tmp_path, """
[model]
name = "my_model"
land_use_types = ["f", "d"]

[model.parameters]
n_steps = 7
""")
        params, spec = _load_toml(toml_path)
        assert params["land_use_types"] == ["f", "d"]
        assert params["n_steps"] == 7
        # spec (-> resolved_spec) keeps carrying the full [model] table too
        assert spec["land_use_types"] == ["f", "d"]

    def test_list_of_tables_merges_into_params(self, tmp_path):
        """[[model.potential]] etc. -- list-of-tables sections used by
        real executors for regression coefficients -- must reach
        params just like scalar/list keys do."""
        toml_path = self._write(tmp_path, """
[model]
name = "my_model"

[[model.potential]]
const = 0.74

[[model.potential]]
const = 0.27
""")
        params, _ = _load_toml(toml_path)
        assert params["potential"] == [{"const": 0.74}, {"const": 0.27}]

    def test_registration_metadata_is_excluded_from_params(self, tmp_path):
        """executor_module/name/class/description/package/dissmodel are
        registration metadata for dissmodel-configs, not simulation
        input -- must stay out of record.parameters."""
        toml_path = self._write(tmp_path, """
[model]
executor_module = "my_package.executors"
name            = "my_model"
class           = "my_model"
description     = "a test model"
package         = "git+https://example.com/my_package@main"
dissmodel       = ">=0.6.0,<0.7.0"

[model.parameters]
n_steps = 7
""")
        params, spec = _load_toml(toml_path)
        assert set(params) == {"n_steps"}
        # still recorded in spec/resolved_spec for provenance
        assert spec["package"] == "git+https://example.com/my_package@main"

    def test_model_parameters_wins_on_overlap(self, tmp_path):
        """[model.parameters] is the run-specific layer and must win
        over a same-named [model]-level default."""
        toml_path = self._write(tmp_path, """
[model]
name = "my_model"
n_steps = 3

[model.parameters]
n_steps = 7
""")
        params, _ = _load_toml(toml_path)
        assert params["n_steps"] == 7

    def test_land_use_types_dict_table_is_normalized(self, tmp_path):
        """land_use_types declared as a dict-table
        ([model.land_use_types] types = [...]) instead of a plain list
        must normalize to a list in params too, not just in spec."""
        toml_path = self._write(tmp_path, """
[model]
name = "my_model"

[model.land_use_types]
types = ["f", "d", "outros"]
""")
        params, spec = _load_toml(toml_path)
        assert params["land_use_types"] == ["f", "d", "outros"]
        assert spec["land_use_types"] == ["f", "d", "outros"]

    def test_no_model_parameters_table_still_merges_model_level_keys(self, tmp_path):
        """A model.toml with no [model.parameters] at all (everything
        declared at the [model] level) must still populate params --
        not every registration TOML has run-specific overrides."""
        toml_path = self._write(tmp_path, """
[model]
name = "my_model"
land_use_types = ["f", "d"]
""")
        params, _ = _load_toml(toml_path)
        assert params["land_use_types"] == ["f", "d"]


# ── _build_record ────────────────────────────────────────────────────────────

class TestBuildRecordTomlMerge:
    """End-to-end: --toml through to the ExperimentRecord actually
    passed to an executor's validate()/load()/run()."""

    def test_model_level_keys_reach_record_parameters(self, tmp_path):
        path = tmp_path / "model.toml"
        path.write_text("""
[model]
name = "my_model"
land_use_types = ["f", "d", "outros"]
static = { f = -1, d = -1, outros = 1 }

[model.parameters]
n_steps = 7
""")
        args = SimpleNamespace(
            toml=str(path), param=None, input="data.zip", output=None,
            format="auto", column_map=None, band_map=None,
        )
        record = _build_record(args)
        assert record.parameters["land_use_types"] == ["f", "d", "outros"]
        assert record.parameters["static"] == {"f": -1, "d": -1, "outros": 1}
        assert record.parameters["n_steps"] == 7
        # resolved_spec keeps the full [model] table for provenance
        assert record.resolved_spec["model"]["name"] == "my_model"

    def test_cli_param_still_overrides_toml(self, tmp_path):
        path = tmp_path / "model.toml"
        path.write_text("""
[model]
name = "my_model"

[model.parameters]
n_steps = 7
""")
        args = SimpleNamespace(
            toml=str(path), param=["n_steps=3"], input="data.zip", output=None,
            format="auto", column_map=None, band_map=None,
        )
        record = _build_record(args)
        assert record.parameters["n_steps"] == 3


# ── _apply_output_path_intelligence ──────────────────────────────────────────

class TestOutputPathIntelligence:

    def _run(self, make_record, output_path: str):
        record          = make_record()
        record.output_path = output_path
        args            = SimpleNamespace(output=output_path)
        _apply_output_path_intelligence(record, args)
        return record, args

    # Scenario A — directory paths

    def test_trailing_slash_generates_filename(self, make_record):
        record, _ = self._run(make_record, "outputs/")
        exp_id = record.experiment_id[:8]
        assert record.output_path == f"outputs/simulacao_{exp_id}.tif"

    def test_existing_directory_generates_filename(self, make_record, tmp_path):
        record          = make_record()
        record.output_path = str(tmp_path)   # tmp_path is a real existing directory
        args            = SimpleNamespace(output=str(tmp_path))
        _apply_output_path_intelligence(record, args)
        exp_id = record.experiment_id[:8]
        assert record.output_path == str(tmp_path / f"simulacao_{exp_id}.tif")

    # Scenario B — file paths without experiment ID

    def test_file_without_id_gets_id_injected(self, make_record):
        record, _ = self._run(make_record, "outputs/result.tif")
        exp_id = record.experiment_id[:8]
        assert record.output_path == f"outputs/result_{exp_id}.tif"

    def test_extension_is_preserved_after_id_injection(self, make_record):
        record, _ = self._run(make_record, "outputs/result.gpkg")
        assert record.output_path.endswith(".gpkg")

    def test_file_already_containing_id_is_not_modified(self, make_record):
        record     = make_record()
        exp_id     = record.experiment_id[:8]
        original   = f"outputs/result_{exp_id}.tif"
        record.output_path = original
        args       = SimpleNamespace(output=original)
        _apply_output_path_intelligence(record, args)
        assert record.output_path == original

    # args.output synchronisation

    def test_args_output_is_synced_after_scenario_a(self, make_record):
        record, args = self._run(make_record, "outputs/")
        assert args.output == record.output_path

    def test_args_output_is_synced_after_scenario_b(self, make_record):
        record, args = self._run(make_record, "outputs/result.tif")
        assert args.output == record.output_path

    # No-op when output_path is not set

    def test_no_output_path_is_noop(self, make_record):
        record          = make_record()
        record.output_path = None
        args            = SimpleNamespace(output=None)
        _apply_output_path_intelligence(record, args)
        assert record.output_path is None
        assert args.output is None