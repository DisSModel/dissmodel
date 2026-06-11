from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class DataSource(BaseModel):
    type:       str = "local"   # 'local' | 's3' | 'http' | 'bdc_stac'
    uri:        str = ""
    collection: str = ""
    version:    str = ""
    checksum:   str = ""


class ExperimentRecord(BaseModel):
    # Identidade
    experiment_id: str      = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    # timezone.utc (not datetime.UTC) — the project supports Python 3.10.
    created_at:    datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Proveniência
    model_name:    str  = ""
    model_commit:  str  = ""
    code_version:  str  = ""
    resolved_spec: dict = {}

    # Input
    source:       DataSource = Field(default_factory=DataSource)
    input_format: str        = "auto"
    column_map:   dict       = {}
    band_map:     dict       = {}
    parameters:   dict       = {}

    # Temporal window used to select driver slices from the cube.
    # None means all variables were loaded as static (no time axis).
    # Together with the derivation spec_hash, this field fully determines
    # which data fed the simulation — required for reproducibility.
    # Example: ("2000", "2014")
    period: tuple[str, str] | None = None

    # Output
    output_path: str | None = None

    artifacts: dict[str, str] = {}
    # Ex: {"output": "sha256...", "report": "sha256...", "plot": "sha256..."}
    # Chave "output" é a principal — usada para verificação de reprodutibilidade.

    metrics: dict = {}
    status:  str  = "pending"
    logs:    list[str] = []

    # ── compatibilidade com executors existentes ──────────────────────────────

    @property
    def output_sha256(self) -> str | None:
        """Compat: retorna artifacts["output"] se existir."""
        return self.artifacts.get("output")

    @output_sha256.setter
    def output_sha256(self, value: str | None) -> None:
        """Compat: salva em artifacts["output"] — executors antigos continuam funcionando."""
        if value is not None:
            self.artifacts["output"] = value

    # ── helpers ───────────────────────────────────────────────────────────────

    def add_log(self, msg: str) -> None:
        self.logs.append(msg)

    def add_artifact(self, name: str, checksum: str) -> None:
        """
        Registra um artefato com seu checksum.

        Uso no executor:
            record.add_artifact("report", write_text(md, uri))
            record.add_artifact("plot",   write_bytes(buf, uri))
            record.add_artifact("output", write_bytes(tif, uri))
        """
        self.artifacts[name] = checksum


class JobRequest(BaseModel):
    """Payload for POST /submit_job (platform only)."""

    model_name:    str
    input_dataset: str
    input_format:  Literal["tiff", "vector", "auto"] = "auto"
    parameters:    dict = {}
    column_map:    dict = {}
    band_map:      dict = {}
    priority:      Literal["low", "normal", "high"] = "normal"


class JobResponse(BaseModel):
    """Response for POST /submit_job and GET /job/{id} (platform only)."""

    job_id:        str
    experiment_id: str
    status:        str
    model_name:    str
    created_at:    datetime
    output_path:   str | None = None
    output_sha256: str | None = None
    input_sha256:  str | None = None
    logs:          list[str]  = []


class InlineJobRequest(BaseModel):
    """
    Payload for POST /submit_job_inline (platform only).

    Accepts a raw TOML string instead of a registered model name.
    Results are not reproducible via the registry — for exploration only.
    """

    input_dataset:   str
    model_spec_toml: str
    input_format:    Literal["tiff", "vector", "auto"] = "auto"
    parameters:      dict = {}
    column_map:      dict = {}
    band_map:        dict = {}
