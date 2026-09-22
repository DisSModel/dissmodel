from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from dissmodel.executor.schemas import ExperimentRecord


class ModelExecutor(ABC):
    """
    Base interface for DisSModel executors.

    Subclasses register themselves automatically in ExecutorRegistry
    via __init_subclass__ — no boilerplate required.

    The platform orchestrates the full lifecycle in order:

        validate(record)          # stateless pre-flight checks
        data = load(record)       # I/O — called once by the platform
        result = run(data, record) # simulation — no I/O here
        record = save(result, record)

    Minimal implementation
    ----------------------
    class MyExecutor(ModelExecutor):
        name = "my_model"

        def load(self, record: ExperimentRecord):
            return gpd.read_file(record.source.uri)

        def run(self, data, record: ExperimentRecord):
            gdf = data  # already loaded — no I/O here
            # ... run simulation ...
            return gdf

        def save(self, result, record: ExperimentRecord) -> ExperimentRecord:
            record.status = "completed"
            return record

    CLI usage
    ---------
    if __name__ == "__main__":
        from dissmodel.executor.cli import run_cli
        run_cli(MyExecutor)
    """

    # Static class attribute — the registry key.
    # Must be a plain string, never a property.
    name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        from .registry import ExecutorRegistry
        if hasattr(cls, "name"):
            ExecutorRegistry.register(cls)

    # ── Required lifecycle methods ────────────────────────────────────────────

    @abstractmethod
    def load(self, record: ExperimentRecord) -> Any:
        """
        Load and resolve the input dataset.

        Called by the platform before run(). The return value is passed
        directly as the first argument to run() — no second load occurs.

        Responsibilities:
        - Resolve URI (s3://, http://, local path)
        - Apply column_map (vector) or band_map (raster)
        - Fill record.source.checksum with sha256 of the loaded data
        - Return data in the format expected by run()
        """

    @abstractmethod
    def run(self, data: Any, record: ExperimentRecord) -> Any:
        """
        Execute the simulation.

        `data` is the direct return value of load(), injected by the platform.
        No I/O should happen here — all loading is done by load().

        Receives record with resolved_spec and parameters already merged.
        Returns raw result — format defined by the subclass and
        consumed by save().
        """

    @abstractmethod
    def save(self, result: Any, record: ExperimentRecord) -> ExperimentRecord:
        """
        Persist the result and return the updated record.

        Responsibilities:
        - Save output to destination (local path or s3://)
        - Fill record.output_path and record.output_sha256
        - Set record.status = "completed"
        - Return the complete record
        """

    # ── Optional hook ─────────────────────────────────────────────────────────

    def validate(self, record: ExperimentRecord) -> None:
        """
        Stateless pre-flight checks on the record — no data loading.

        Called by the platform before load(). Override to check canonical
        columns/bands, value ranges, parameter constraints, etc.
        Raise ValueError with an actionable message if invalid.

        Default implementation: no-op.
        """

    # ── Utilities available to subclasses ─────────────────────────────────────

    def _resolve_uri(self, uri: str) -> str:
        """
        Resolve any URI to a local path accessible by the executor.

        s3://bucket/key  → downloads to /tmp/<filename>, returns path
        http(s)://...    → downloads to /tmp/<filename>, returns path
        /local/path      → returns as-is
        """
        import os
        import urllib.request

        if uri.startswith("s3://"):
            from dissmodel.io._storage import get_default_client
            minio       = get_default_client()
            bucket, key = uri[5:].split("/", 1)
            local_path  = f"/tmp/{os.path.basename(key)}"
            minio.fget_object(bucket, key, local_path)
            return local_path

        if uri.startswith(("http://", "https://")):
            filename   = uri.split("/")[-1].split("?")[0]
            local_path = f"/tmp/{filename}"
            urllib.request.urlretrieve(uri, local_path)
            return local_path

        return uri

    @staticmethod
    def _sha256(path_or_bytes) -> str:
        """Compute sha256 of a file path or bytes."""
        import hashlib
        if isinstance(path_or_bytes, bytes):
            return hashlib.sha256(path_or_bytes).hexdigest()
        with open(path_or_bytes, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
