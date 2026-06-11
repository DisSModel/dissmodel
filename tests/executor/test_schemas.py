"""
tests/executor/test_schemas.py
===============================
Tests for ExperimentRecord fields added/changed on the backend-3d branch:

- ``period``: temporal window used to select driver slices from the cube
  (None = all variables loaded as static). Part of the provenance contract.
- ``created_at``: timezone-aware UTC factory (replaces deprecated utcnow).
"""
from __future__ import annotations

import json
from datetime import timezone

import pytest
from pydantic import ValidationError

from dissmodel.executor.schemas import ExperimentRecord


# ── period ────────────────────────────────────────────────────────────────────

class TestPeriodField:

    def test_default_is_none(self):
        assert ExperimentRecord().period is None

    def test_accepts_two_string_tuple(self):
        r = ExperimentRecord(period=("2000", "2014"))
        assert r.period == ("2000", "2014")

    def test_list_input_coerced_to_tuple(self):
        # JSON payloads deserialize tuples as lists — pydantic must coerce
        r = ExperimentRecord(period=["2000", "2014"])
        assert r.period == ("2000", "2014")

    def test_wrong_length_raises(self):
        with pytest.raises(ValidationError):
            ExperimentRecord(period=("2000",))
        with pytest.raises(ValidationError):
            ExperimentRecord(period=("2000", "2010", "2020"))

    def test_json_round_trip(self):
        r = ExperimentRecord(period=("2000", "2014"))
        payload = json.loads(r.model_dump_json())
        assert payload["period"] == ["2000", "2014"]
        restored = ExperimentRecord.model_validate(payload)
        assert restored.period == ("2000", "2014")

    def test_none_serializes_as_null(self):
        payload = json.loads(ExperimentRecord().model_dump_json())
        assert payload["period"] is None


# ── created_at ────────────────────────────────────────────────────────────────

class TestCreatedAt:

    def test_is_timezone_aware_utc(self):
        r = ExperimentRecord()
        assert r.created_at.tzinfo is not None
        assert r.created_at.utcoffset() == timezone.utc.utcoffset(None)

    def test_isoformat_carries_utc_offset(self):
        r = ExperimentRecord()
        assert r.created_at.isoformat().endswith("+00:00")
