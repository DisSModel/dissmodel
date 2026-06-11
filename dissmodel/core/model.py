from __future__ import annotations

import math
from typing import Any

from .environment import Environment


class Model:
    """
    Base class for simulation models.

    Provides a time-stepped execution loop and automatic tracking of
    attributes marked for plotting via the
    :func:`~dissmodel.visualization.track_plot` decorator.

    Every ``Model`` instance auto-registers with the currently active
    :class:`~dissmodel.core.Environment` at construction time. An active
    environment must exist before instantiating any model.

    Parameters
    ----------
    step : float, optional
        Time increment between successive :meth:`execute` calls, by default 1.
    start_time : float, optional
        Time at which the model starts executing, by default 0.
    end_time : float, optional
        Last time at which the model executes (inclusive), by default
        ``math.inf``. The model still executes at ``t == end_time`` and
        stops being scheduled afterwards.
    name : str, optional
        Human-readable model name, by default ``""``.
    **kwargs :
        Extra keyword arguments (ignored; kept for subclass compatibility).

    Raises
    ------
    RuntimeError
        If no active :class:`~dissmodel.core.Environment` exists when the
        model is instantiated.

    Examples
    --------
    >>> class MyModel(Model):
    ...     def execute(self):
    ...         print(self.env.now())
    >>> env = Environment(start_time=0, end_time=5)
    >>> model = MyModel(step=1)
    >>> env.run()
    Running from 0 to 5 (duration: 5)
    0
    1
    2
    3
    4
    5
    """

    # Declared here because __init__ assigns them via object.__setattr__
    # (to bypass the plot-tracking __setattr__), which static checkers
    # cannot see.
    name: str
    start_time: float
    end_time: float
    env: Environment
    _step: float
    _next_time: float

    def __init__(
        self,
        step: float = 1,
        start_time: float = 0,
        end_time: float = math.inf,
        name: str = "",
        **kwargs: Any,
    ) -> None:
        env = Environment._current
        if env is None:
            raise RuntimeError(
                "No active Environment found. "
                "Create an Environment before instantiating a Model."
            )

        # Set internal attributes directly to avoid triggering __setattr__
        # plot-tracking logic before _plot_info is available.
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "_step", step)
        object.__setattr__(self, "start_time", start_time)
        object.__setattr__(self, "end_time", end_time)
        object.__setattr__(self, "_next_time", start_time)
        object.__setattr__(self, "env", env)

        env._register(self)
        self.setup(**kwargs)

    def setup(self, **kwargs: Any) -> None:
        """
        Called once after instantiation, receiving any extra keyword
        arguments not consumed by ``__init__``.

        Override in subclasses to perform one-time setup such as building
        neighborhoods or initializing visualization state.
        """
        pass

    def pre_execute(self) -> None:
        """
        Called once before each :meth:`execute`.

        Override in subclasses to perform per-step setup, such as
        snapshotting state arrays before the transition rule runs.
        """
        pass

    def execute(self) -> None:
        """
        Called once per time step.

        Override in subclasses to define model behaviour.
        """
        pass

    def post_execute(self) -> None:
        """
        Called once after each :meth:`execute`.

        Override in subclasses to perform per-step cleanup or snapshotting
        after the transition rule runs.
        """
        pass

    # ------------------------------------------------------------------
    # Plot tracking
    # ------------------------------------------------------------------

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Intercept attribute assignment to record values marked for plotting.

        If the class defines ``_plot_info`` (populated by the
        :func:`~dissmodel.visualization.track_plot` decorator) and ``name``
        matches a tracked attribute, the value is appended to the plot data
        buffer and registered in ``env._plot_metadata``.

        Parameters
        ----------
        name : str
            Attribute name being set.
        value : Any
            Value being assigned.
        """
        cls = self.__class__

        if hasattr(cls, "_plot_info") and name.lower() in cls._plot_info:
            plot_info: dict[str, Any] = cls._plot_info[name.lower()]
            plot_info["data"].append(value)

            env = Environment._current
            if env is not None and plot_info["label"] not in env._plot_metadata:
                env._plot_metadata[plot_info["label"]] = plot_info

        super().__setattr__(name, value)
