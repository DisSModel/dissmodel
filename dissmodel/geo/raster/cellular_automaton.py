"""
dissmodel/geo/raster_cellular_automaton.py
==========================================
Base class for cellular automata backed by RasterBackend (NumPy 2D arrays).

Analogous to CellularAutomaton (GeoDataFrame), but for the raster substrate.

Hierarchy
---------
    Model
      ├── SpatialModel
      │     └── CellularAutomaton       rule(idx) → value       (vector, pull)
      └── RasterModel
            └── RasterCellularAutomaton rule(arrays) → arrays   (raster, vectorized)

Why a different rule() contract
--------------------------------
CellularAutomaton.rule(idx) returns a single value for one cell — it is
called once per cell per step (O(n) Python calls). This is correct for
the vector substrate where neighborhood lookup is the bottleneck.

For the raster substrate, the bottleneck is the Python loop itself.
RasterCellularAutomaton.rule() receives the full snapshot of all arrays
and returns a dict of updated arrays — one NumPy call covers the entire
grid. This is the natural pattern for NumPy-based CA.

Comparison
----------
    # vector CA — rule called n times per step
    class GameOfLife(CellularAutomaton):
        def rule(self, idx):
            alive = self.neighbor_values(idx, "state").sum()
            ...
            return new_state

    # raster CA — rule called once per step
    class GameOfLife(RasterCellularAutomaton):
        def rule(self, arrays):
            state = arrays["state"]
            alive = backend.focal_sum_mask(state == 1)
            ...
            return {"state": new_state}

Usage
-----
    from dissmodel.geo.raster_cellular_automaton import RasterCellularAutomaton
    from dissmodel.geo.raster.backend import RasterBackend
    from dissmodel.core import Environment
    import numpy as np

    class GameOfLife(RasterCellularAutomaton):
        def rule(self, arrays):
            state     = arrays["state"]
            neighbors = self.backend.focal_sum_mask(state == 1)
            born      = (state == 0) & (neighbors == 3)
            survive   = (state == 1) & np.isin(neighbors, [2, 3])
            return {"state": np.where(born | survive, 1, 0)}

    b = RasterBackend(shape=(50, 50))
    b.set("state", np.random.randint(0, 2, (50, 50)))

    env = Environment(start_time=1, end_time=100)
    GameOfLife(backend=b)
    env.run()
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from dissmodel.geo.raster.raster_model import RasterModel
from dissmodel.geo.raster.backend import RasterBackend


class RasterCellularAutomaton(RasterModel, ABC):
    """
    Base class for NumPy-based cellular automata.

    Extends :class:`~dissmodel.geo.raster.model.RasterModel` with a
    vectorized transition rule — ``rule()`` receives all arrays as a
    snapshot and returns a dict of updated arrays.

    Parameters
    ----------
    backend : RasterBackend
        Shared backend with the simulation arrays.
    state_attr : str, optional
        Primary state array name, by default ``"state"``.
        Used only for introspection/logging — rule() can update any array.
    **kwargs :
        Extra keyword arguments forwarded to RasterModel.

    Examples
    --------
    >>> class MyCA(RasterCellularAutomaton):
    ...     def rule(self, arrays):
    ...         state = arrays["state"]
    ...         # ... NumPy operations over full grid ...
    ...         return {"state": new_state}
    """

    # Narrowing the base Model.setup(**kwargs) contract is intentional:
    # Model.__init__ forwards extra kwargs to setup, and each component
    # declares the keywords it accepts.
    def setup(  # type: ignore[override]
        self,
        backend:    RasterBackend,
        state_attr: str = "state"
    ) -> None:
        super().setup(backend)
        self.state_attr = state_attr

    @abstractmethod
    def rule(self, arrays: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
        """
        Vectorized transition rule applied to the full grid.

        Receives a snapshot of all arrays (equivalent to celula.past[] in
        TerraME) and returns a dict with the arrays to update.

        Only the arrays present in the returned dict are written back —
        arrays not returned are left unchanged.

        Parameters
        ----------
        arrays : dict[str, np.ndarray]
            Snapshot of backend arrays at the start of the step.
            Modifying these arrays does NOT affect the backend — they are
            copies (equivalent to .past semantics).

        Returns
        -------
        dict[str, np.ndarray]
            Dict mapping array name → new array. Partial updates allowed.

        Examples
        --------
        >>> def rule(self, arrays):
        ...     state     = arrays["state"]           # read from snapshot
        ...     neighbors = self.backend.focal_sum_mask(state == 1)
        ...     new_state = np.where(neighbors > 3, 0, state)
        ...     return {"state": new_state}           # write back
        """
        raise NotImplementedError("Subclasses must implement rule().")

    def execute(self) -> None:
        """
        Execute one simulation step by calling rule() once over the full grid.

        Takes a snapshot of all arrays (past state), passes it to rule(),
        and writes the returned arrays back to the backend.
        """
        past    = self.backend.snapshot()   # equivale a celula.past[]
        updates = self.rule(past)
        for name, arr in updates.items():
            self.backend.arrays[name] = arr
