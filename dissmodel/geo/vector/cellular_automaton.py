"""
dissmodel/geo/cellular_automaton.py
=====================================
Base class for spatial cellular automata backed by a GeoDataFrame.

Extends :class:`~dissmodel.geo.spatial_model.SpatialModel` with a
cell-by-cell transition rule loop.

For source-oriented (push) models that cannot use rule(idx), inherit
:class:`~dissmodel.geo.spatial_model.SpatialModel` directly and implement
execute() freely.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

import geopandas as gpd

from dissmodel.geo.vector.spatial_model import SpatialModel


class CellularAutomaton(SpatialModel, ABC):
    """
    Base class for spatial cellular automata backed by a GeoDataFrame.

    Extends :class:`~dissmodel.geo.spatial_model.SpatialModel` with
    neighborhood management and a cell-by-cell transition rule loop.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame with geometries and a state attribute.
    state_attr : str, optional
        Column name representing the cell state, by default ``"state"``.
    step : float, optional
        Time increment per execution step, by default 1.
    start_time : float, optional
        Simulation start time, by default 0.
    end_time : float, optional
        Simulation end time, by default ``math.inf``.
    name : str, optional
        Optional model name, by default ``""``.
    dim : tuple of int, optional
        Grid dimensions as ``(n_cols, n_rows)``, by default ``None``.
    **kwargs :
        Extra keyword arguments forwarded to
        :class:`~dissmodel.geo.spatial_model.SpatialModel`.

    Examples
    --------
    >>> class MyCA(CellularAutomaton):
    ...     def rule(self, idx):
    ...         return self.gdf.loc[idx, self.state_attr]
    """

    def __init__(
        self,
        gdf: gpd.GeoDataFrame,
        state_attr: str = "state",
        step: float = 1,
        start_time: float = 0,
        end_time: float = math.inf,
        name: str = "",
        dim: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.state_attr = state_attr
        self.dim        = dim
        super().__init__(
            gdf=gdf,
            step=step,
            start_time=start_time,
            end_time=end_time,
            name=name,
            **kwargs,
        )
        

    def initialize(self) -> None:
        """
        Set up the initial model state.

        Override in subclasses to define the starting conditions.
        """

    @abstractmethod
    def rule(self, idx: Any) -> Any:
        """
        Transition rule applied to each cell.

        Must be overridden in subclasses to define the state transition logic.

        Parameters
        ----------
        idx : any
            Index of the cell being evaluated.

        Returns
        -------
        any
            New state value for the cell.

        Raises
        ------
        NotImplementedError
            If not overridden by the subclass.
        """
        raise NotImplementedError("Subclasses must implement the transition rule.")

    def execute(self) -> None:
        """
        Execute one simulation step by applying :meth:`rule` to every cell.

        Raises
        ------
        RuntimeError
            If the neighborhood has not been created yet.

        Notes
        -----
        Because :meth:`rule` is an arbitrary Python function, the update
        cannot be vectorized automatically. Performance-critical subclasses
        should prefer :meth:`neighbor_values` over :meth:`neighs` inside
        ``rule`` to avoid geometry overhead on every lookup.
        """
        if not self._neighborhood_created:
            raise RuntimeError(
                "Neighborhood must be created before running the model. "
                "Call `.create_neighborhood()` first."
            )
        self.gdf[self.state_attr] = self.gdf.index.map(self.rule)
