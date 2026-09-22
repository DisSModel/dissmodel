from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from dissmodel.executor.model_executor import ModelExecutor


class ExecutorRegistry:
    """
    Central registry mapping model names to executor classes.

    Registration is automatic — subclasses of ModelExecutor register
    themselves via __init_subclass__ without any boilerplate.
    """

    _executors: ClassVar[dict[str, type[ModelExecutor]]] = {}

    @classmethod
    def register(cls, executor_cls: type[ModelExecutor]) -> None:
        """Called automatically by ModelExecutor.__init_subclass__."""
        cls._executors[executor_cls.name] = executor_cls

    @classmethod
    def get(cls, name: str) -> type[ModelExecutor]:
        """
        Resolve executor class by name.
        Raises KeyError with a clear message if not registered.
        """
        if name not in cls._executors:
            available = ", ".join(cls._executors) or "none"
            raise KeyError(
                f"Executor '{name}' not registered. "
                f"Available: {available}"
            )
        return cls._executors[name]

    @classmethod
    def list(cls) -> list[str]:
        """Return all registered executor names."""
        return list(cls._executors.keys())
