from __future__ import annotations

import inspect
import traceback
from typing import TYPE_CHECKING

from .schemas import DataSource, ExperimentRecord

if TYPE_CHECKING:
    from dissmodel.executor.model_executor import ModelExecutor


class ExecutorTestHarness:
    """
    Validates that an executor fulfills the ModelExecutor contract.

    Designed to run in Jupyter before opening a PR — the same checks
    are reused in CI via pytest parametrize, so a passing notebook
    guarantees a passing pipeline.

    Usage
    -----
    harness = ExecutorTestHarness(MyExecutor)
    harness.run_contract_tests()          # structural — no data needed
    harness.run_with_sample_data(record)  # full cycle with real data
    """

    def __init__(self, executor_cls: type[ModelExecutor]) -> None:
        self.executor_cls = executor_cls
        self.executor     = executor_cls()
        self._passed: list[str] = []
        self._failed: list[str] = []

    # ── Public interface ──────────────────────────────────────────────────────

    def run_contract_tests(self) -> bool:
        """
        Run structural checks — no data required.
        Returns True if all checks pass.
        """
        self._passed.clear()
        self._failed.clear()

        self._check("name attribute exists",      self._check_name_exists)
        self._check("name is a non-empty string", self._check_name_type)
        self._check("name has no whitespace",      self._check_name_format)
        self._check("load() is implemented",       self._check_load)
        self._check("run() is implemented",        self._check_run)
        self._check("save() is implemented",       self._check_save)
        self._check("run() signature is correct",  self._check_run_signature)
        self._check("save() signature is correct", self._check_save_signature)

        self._print_report()
        return len(self._failed) == 0

    def run_with_sample_data(self, record: ExperimentRecord | None = None) -> bool:
        """
        Run the full executor lifecycle with real or synthetic data.

        Calls validate → load → run(data, record) → save in sequence.
        Returns True if the cycle completes without error.
        """
        if record is None:
            record = self._minimal_record()
            print("  No record provided — using minimal synthetic record")

        print(f"\n▶ Running {self.executor_cls.name}...")

        try:
            print("  validate()...")
            self.executor.validate(record)

            print("  load()...")
            data = self.executor.load(record)

            print("  run()...")
            result = self.executor.run(data, record)

            print("  save()...")
            completed = self.executor.save(result, record)

            if completed.status != "completed":
                print(f"  ⚠ save() returned status='{completed.status}' — expected 'completed'")
                return False

            if not completed.output_sha256:
                print("  ⚠ save() did not set output_sha256")
                return False

            print(f"  ✅ Cycle OK — status={completed.status}  sha256={completed.output_sha256[:12]}...")
            return True

        except NotImplementedError:
            print("  ⚠ Some methods are not yet implemented")
            return False

        except Exception:  # noqa: BLE001 — test harness: any model failure must be reported, not crash the run; traceback is printed above
            print(f"  ❌ Error during execution:\n{traceback.format_exc()}")
            return False

    # ── Individual checks ─────────────────────────────────────────────────────

    def _check_name_exists(self) -> None:
        assert hasattr(self.executor_cls, "name"), \
            "Class must define a 'name' class attribute"

    def _check_name_type(self) -> None:
        assert isinstance(self.executor_cls.name, str) and self.executor_cls.name, \
            f"'name' must be a non-empty string, got {self.executor_cls.name!r}"

    def _check_name_format(self) -> None:
        assert " " not in self.executor_cls.name, \
            f"'name' must not contain whitespace: {self.executor_cls.name!r}"

    def _check_load(self) -> None:
        assert not _is_abstract(self.executor, "load"), \
            "load() must be implemented"

    def _check_run(self) -> None:
        assert not _is_abstract(self.executor, "run"), \
            "run() must be implemented"

    def _check_save(self) -> None:
        assert not _is_abstract(self.executor, "save"), \
            "save() must be implemented"

    def _check_run_signature(self) -> None:
        sig    = inspect.signature(self.executor.run)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        assert len(params) == 2, (
            f"run() must accept exactly two parameters (data, record), "
            f"got {[p.name for p in params]}. "
            f"Did you update to the 0.4.0 signature?"
        )

    def _check_save_signature(self) -> None:
        sig    = inspect.signature(self.executor.save)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        assert len(params) == 2, \
            f"save() must accept exactly two parameters (result, record), got {[p.name for p in params]}"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _check(self, label: str, fn) -> None:
        try:
            fn()
            self._passed.append(label)
        except AssertionError as exc:
            self._failed.append(f"{label}: {exc}")
        except Exception as exc:  # noqa: BLE001 — test harness: any check failure must be recorded, not crash the run; message is captured above
            self._failed.append(f"{label}: unexpected error — {exc}")

    def _print_report(self) -> None:
        print(f"\nExecutorTestHarness — {self.executor_cls.__name__}")
        print("─" * 52)
        for label in self._passed:
            print(f"  ✅ {label}")
        for label in self._failed:
            print(f"  ❌ {label}")
        print("─" * 52)
        if self._failed:
            print(f"  {len(self._passed)} passed, {len(self._failed)} failed\n")
        else:
            print(f"  All {len(self._passed)} checks passed ✅\n")

    def _minimal_record(self) -> ExperimentRecord:
        """Synthetic record for contract testing without real data."""
        return ExperimentRecord(
            model_name    = getattr(self.executor_cls, "name", "unknown"),
            model_commit  = "local-test",
            code_version  = "dev",
            resolved_spec = {"model": {"class": getattr(self.executor_cls, "name", ""), "parameters": {}}},
            source        = DataSource(type="local", uri=""),
        )


def _is_abstract(obj: object, method_name: str) -> bool:
    """Return True if a method is still abstract on the given instance."""
    method = getattr(type(obj), method_name, None)
    return getattr(method, "__isabstractmethod__", False)
