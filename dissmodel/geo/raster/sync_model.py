"""
dissmodel/geo/raster/sync_model.py
=====================================
SyncRasterModel — RasterModel with automatic _past snapshot semantics.

This module provides the snapshot mechanism equivalent to TerraME's
``cs:synchronize()``, as a reusable base class for any raster model that
needs per-step state history (LUCC, fire spread, epidemic models, etc.).

How it works
------------
Before the first ``execute()``, ``pre_execute()`` calls ``synchronize()``
once to capture the initial state. After each ``execute()``,
``post_execute()`` calls ``synchronize()`` again to freeze the current
state as ``<name>_past`` for the next step.

Models can call ``self.backend.get("f_past")`` inside ``execute()`` to
access the state at the beginning of the current step — equivalent to
TerraME's ``cell.past[attr]``.

Usage
-----
Subclass ``SyncRasterModel`` instead of ``RasterModel`` and declare
``self.land_use_types`` in ``setup()``:

    class MyRasterModel(SyncRasterModel):
        def setup(self, backend, rate=0.01):
            super().setup(backend)
            self.land_use_types = ["forest", "defor"]
            self.rate = rate

        def execute(self):
            forest_past = self.backend.get("forest_past")
            gain = forest_past * self.rate
            self.backend.arrays["forest"] = forest_past + gain

Relationship to domain libraries
----------------------------------
``dissluc`` uses this class as the base for its raster LUCC components,
exposing it under the domain-specific alias ``LUCRasterModel``:

    # dissluc/raster/core.py
    from dissmodel.geo.raster.sync_model import SyncRasterModel as LUCRasterModel
"""
from __future__ import annotations

# import from the defining module (not the dissmodel.geo package) to avoid
# a circular import while dissmodel.geo.__init__ is still initializing
from dissmodel.geo.raster.raster_model import RasterModel


class SyncRasterModel(RasterModel):
    """
    ``RasterModel`` with automatic ``_past`` snapshot semantics.

    Extends :class:`~dissmodel.geo.raster.model.RasterModel` with
    ``pre_execute()`` / ``post_execute()`` hooks that copy each array
    listed in ``self.land_use_types`` to a ``<name>_past`` array in the
    :class:`~dissmodel.geo.raster.backend.RasterBackend` before and after
    every simulation step.

    This is the raster analogue of
    :class:`~dissmodel.geo.vector.sync_model.SyncSpatialModel` and the
    Python equivalent of TerraME's ``cs:synchronize()``.

    Subclass contract
    -----------------
    Declare ``self.land_use_types`` (list of array names) in ``setup()``.
    ``SyncRasterModel`` will manage all ``<name>_past`` arrays automatically.
    Subclasses must **not** create or update ``_past`` arrays manually.

    The ``backend`` argument is passed through to
    :class:`~dissmodel.geo.raster.model.RasterModel`; any additional keyword
    arguments are forwarded to the parent class.

    Examples
    --------
    >>> class ForestRaster(SyncRasterModel):
    ...     def setup(self, backend, rate=0.01):
    ...         super().setup(backend)
    ...         self.land_use_types = ["forest", "defor"]
    ...         self.rate = rate
    ...
    ...     def execute(self):
    ...         forest_past = self.backend.get("forest_past")
    ...         gain = forest_past * self.rate
    ...         self.backend.arrays["forest"] = forest_past + gain
    """

    def pre_execute(self) -> None:
        """
        Snapshot arrays before the first step.

        On the first call, freezes the initial state into ``<name>_past``
        arrays so that ``execute()`` can read them. Subsequent calls are
        no-ops — post_execute() handles ongoing snapshots.
        """
        if not getattr(self, "_first_sync_done", False):
            self.synchronize()
            self._first_sync_done = True

    def post_execute(self) -> None:
        """
        Snapshot arrays after each step.

        Freezes the current state into ``<name>_past`` arrays so that
        the next ``execute()`` call reads the state at step start —
        equivalent to TerraME's ``cs:synchronize()``.
        """
        self.synchronize()

    def synchronize(self) -> None:
        """
        Copy each array in ``land_use_types`` to ``<name>_past`` in the backend.

        Equivalent to ``cs:synchronize()`` in TerraME. Called automatically
        via ``pre_execute()`` before the first step and via ``post_execute()``
        after each ``execute()``. Can also be called manually when an explicit
        mid-step snapshot is needed.

        Does nothing if ``land_use_types`` has not been set yet (safe to
        call before ``setup()`` completes).
        """
        if not hasattr(self, "land_use_types"):
            return
        for name in self.land_use_types:
            self.backend.set(name + "_past", self.backend.get(name).copy())
