"""
dissmodel/geo/raster/backend.py
================================
Vectorized engine for cellular automata on raster grids (NumPy 2D arrays).

Responsibility
--------------
Provide generic spatial operations (shift, dilate, focal_sum, snapshot)
with no domain knowledge — no land-use classes, no CRS, no I/O, no
project-specific constants.

Domain models (FloodRasterModel, MangroveRasterModel, …) import
RasterBackend and operate on named arrays stored in ``self.arrays``.

Temporal variables
------------------
Arrays may be static ``(y, x)`` or temporal ``(time, y, x)``.
Static variables are stored without a time axis and behave exactly as before.
Temporal variables are stored with an explicit time coordinate array
in ``self.time_coords``.

    # static — backward compatible
    b.set("slope", slope_arr)
    b.get("slope")                   # → (y, x)

    # temporal
    b.set("dist_roads", roads_arr, time=np.array([2000, 2014, 2020]))
    b.get("dist_roads")              # → (time, y, x) full series
    b.get("dist_roads", time=2014)   # → (y, x) slice at 2014

CA models always call ``get(name, time=step)`` or ``get(name)`` for static
vars — they never see the time dimension directly.

Minimal example
---------------
    from dissmodel.geo.raster.backend import RasterBackend, DIRS_MOORE

    b = RasterBackend(shape=(100, 100))
    b.set("state", np.zeros((100, 100), dtype=np.int8))

    state    = b.get("state").copy()          # equivalent to cell.past[attr]
    contact  = b.neighbor_contact(state == 1)
    for dr, dc in DIRS_MOORE:
        neighbour = RasterBackend.shift2d(state, dr, dc)
        ...
    b.arrays["state"] = new_state
"""
from __future__ import annotations

from typing import Any

import numpy as np
from scipy.ndimage import binary_dilation


# Moore neighbourhood (8 directions) — framework constant, not domain-specific.
DIRS_MOORE: list[tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, 1),
    ( 0, -1),          ( 0, 1),
    ( 1, -1), ( 1, 0), ( 1, 1),
]

# Von Neumann neighbourhood (4 directions) — available for models that require it.
DIRS_VON_NEUMANN: list[tuple[int, int]] = [
    (-1, 0), (0, -1), (0, 1), (1, 0),
]


class RasterBackend:
    """
    Storage and vectorized operations for 2D raster grids.

    Replaces TerraME's ``forEachCell`` / ``forEachNeighbor`` with pure NumPy
    operations. The backend is shared across multiple models running in the
    same ``Environment`` — each model reads and writes named arrays every step.

    Arrays
    ------
    Stored in ``self.arrays`` as ``np.ndarray`` of shape ``(rows, cols)``
    for static variables, or ``(time, rows, cols)`` for temporal variables.
    No names are reserved — domain models define their own
    (``"uso"``, ``"alt"``, ``"solo"``, ``"state"``, ``"dist_roads"``, …).

    Time coordinates for temporal variables are stored in ``self.time_coords``
    as a parallel dict mapping variable name → 1D ``np.ndarray`` of time values.

    Parameters
    ----------
    shape : tuple[int, int]
        Grid shape as ``(rows, cols)``.
    nodata_value : float | int | None
        Sentinel value used to mark cells outside the study extent.
        When provided, ``nodata_mask`` derives the extent mask automatically.
        Default: ``None``.

    Examples
    --------
    >>> b = RasterBackend(shape=(10, 10))
    >>> b.set("state", np.zeros((10, 10), dtype=np.int8))
    >>> b.get("state").shape
    (10, 10)

    >>> b = RasterBackend(shape=(10, 10), nodata_value=-1)
    >>> b.nodata_mask   # True = valid cell, False = outside extent

    >>> # temporal variable
    >>> b.set("dist_roads", roads_3d, time=np.array([2000, 2014, 2020]))
    >>> b.get("dist_roads", time=2014).shape   # (10, 10)
    >>> b.get("dist_roads").shape              # (3, 10, 10)
    """

    def __init__(
        self,
        shape: tuple[int, int],
        nodata_value: float | int | None = None,
        transform: Any = None,
        crs: Any = None,
    ) -> None:
        self.shape        = shape
        self.arrays: dict[str, np.ndarray] = {}
        self.time_coords: dict[str, np.ndarray] = {}  # name → 1D time axis
        self.nodata_value = nodata_value

        self.transform    = transform
        self.crs          = crs

    # ── temporal helpers ──────────────────────────────────────────────────────

    def is_temporal(self, name: str) -> bool:
        """Return ``True`` if ``name`` has an associated time axis."""
        return name in self.time_coords

    def time_axis(self, name: str) -> np.ndarray | None:
        """Return the time coordinate array for ``name``, or ``None``."""
        return self.time_coords.get(name)

    # ── extent mask ───────────────────────────────────────────────────────────

    @property
    def nodata_mask(self) -> np.ndarray | None:
        """
        Boolean mask: ``True`` = valid cell, ``False`` = outside extent / nodata.

        Derived in priority order:
        1. ``arrays["mask"]``  — explicit mask band.
        2. ``nodata_value``    — applied over the first available static array.
        3. ``None``            — no information.
        """
        if "mask" in self.arrays:
            return self.arrays["mask"] != 0

        if self.nodata_value is not None and self.arrays:
            # use first static (2D) array for the mask
            for arr in self.arrays.values():
                if arr.ndim == 2:
                    return arr != self.nodata_value

        return None

    # ── read / write ──────────────────────────────────────────────────────────

    def set(
        self,
        name: str,
        array: np.ndarray,
        time: np.ndarray | list | None = None,
    ) -> None:
        """
        Store ``array`` under ``name``.

        Parameters
        ----------
        name : str
            Variable name.
        array : np.ndarray
            Shape ``(y, x)`` for static variables, ``(time, y, x)`` for temporal.
        time : array-like | None
            1D sequence of time coordinate values (int or str) matching the
            first dimension of ``array``. If provided, the variable is marked
            as temporal and ``get(name, time=t)`` will return a 2D slice.
            Must be ``None`` for static (2D) arrays.

        Raises
        ------
        ValueError
            If ``time`` length does not match the first dimension of ``array``.
        """
        arr = np.asarray(array).copy()

        if time is not None:
            t = np.asarray(time)
            if arr.ndim != 3:
                raise ValueError(
                    f"Expected 3D array (time, y, x) when time is given, "
                    f"got shape {arr.shape}"
                )
            if len(t) != arr.shape[0]:
                raise ValueError(
                    f"time length ({len(t)}) must match array first dim ({arr.shape[0]})"
                )
            self.time_coords[name] = t
        else:
            # remove any stale time axis when overwriting with static array
            self.time_coords.pop(name, None)

        self.arrays[name] = arr

    def get(
        self,
        name: str,
        time: int | str | None = None,
    ) -> np.ndarray:
        """
        Return array for ``name``.

        Behaviour
        ---------
        - Static variable (no time axis): always returns ``(y, x)``.
          The ``time`` argument is silently ignored, so CA models can call
          ``get(name, time=step)`` uniformly without checking variable type.
        - Temporal variable + ``time=None``: returns full ``(time, y, x)`` series.
        - Temporal variable + ``time=t``: returns ``(y, x)`` slice nearest to ``t``.

        Parameters
        ----------
        name : str
        time : int | str | None
            Time value to select. Uses ``np.searchsorted`` for lookup.

        Raises
        ------
        KeyError
            If ``name`` is not in ``self.arrays``.
        """
        arr = self.arrays[name]

        if time is None or name not in self.time_coords:
            return arr

        idx = int(np.searchsorted(self.time_coords[name], time))
        # clamp to valid range
        idx = max(0, min(idx, arr.shape[0] - 1))
        return arr[idx]

    def snapshot(self) -> dict[str, np.ndarray]:
        """
        Return a deep copy of all arrays — equivalent to TerraME's ``.past`` mechanism.

        For temporal variables the full ``(time, y, x)`` array is copied.
        Use ``get(name, time=t)`` on the backend directly to snapshot a single
        time slice.

        Returns
        -------
        dict[str, np.ndarray]
        """
        return {k: v.copy() for k, v in self.arrays.items()}

    def rename_band(self, old: str, new: str) -> None:
        """
        Rename an array in-place. No-op if ``old`` does not exist.
        Time coordinates are renamed alongside the array.
        """
        if old in self.arrays:
            self.arrays[new] = self.arrays.pop(old)
            if old in self.time_coords:
                self.time_coords[new] = self.time_coords.pop(old)

    # ── xarray interoperability ───────────────────────────────────────────────

    def to_xarray(self, time: int | None = None):
        """
        Convert the backend to an ``xr.Dataset``.

        Static variables become ``DataArray(y, x)``.
        Temporal variables become ``DataArray(time, y, x)`` with explicit
        time coordinates from ``self.time_coords``.

        If ``time`` is given (simulation step), a scalar ``time`` coordinate
        is added to static variables — useful when assembling multi-step outputs.

        Parameters
        ----------
        time : int | None
            Optional simulation step to attach as a scalar coordinate
            (applies to static variables only).

        Returns
        -------
        xr.Dataset
        """
        try:
            import xarray as xr
        except ImportError:
            raise ImportError(
                "xarray is required for RasterBackend.to_xarray(). "
                "Install it with: pip install xarray"
            )

        rows, cols = self.shape

        if self.transform is not None:
            try:
                xs = np.array([self.transform.c + (c + 0.5) * self.transform.a
                                for c in range(cols)])
                ys = np.array([self.transform.f + (r + 0.5) * self.transform.e
                                for r in range(rows)])
            except AttributeError:
                xs = np.arange(cols, dtype=float)
                ys = np.arange(rows, dtype=float)
        else:
            xs = np.arange(cols, dtype=float)
            ys = np.arange(rows, dtype=float)

        base_coords: dict = {"y": ys, "x": xs}

        # CRS as spatial_ref coordinate (CF / rioxarray convention)
        if self.crs is not None:
            try:
                from pyproj import CRS as ProjCRS
                import xarray as xr
                crs_obj = ProjCRS.from_user_input(self.crs)
                base_coords["spatial_ref"] = xr.DataArray(
                    0,
                    attrs={
                        "crs_wkt":      crs_obj.to_wkt(),
                        "grid_mapping": "spatial_ref",
                    },
                )
            except Exception:
                pass

        data_vars = {}
        for name, arr in self.arrays.items():
            attrs: dict = {}
            if self.nodata_value is not None:
                attrs["_FillValue"] = self.nodata_value
            if self.crs is not None and "spatial_ref" in base_coords:
                attrs["grid_mapping"] = "spatial_ref"

            if name in self.time_coords:
                # temporal variable — emit (time, y, x)
                data_vars[name] = xr.DataArray(
                    arr.copy(),
                    dims=["time", "y", "x"],
                    coords={
                        "time": self.time_coords[name],
                        "y": ys,
                        "x": xs,
                    },
                    attrs=attrs,
                )
            else:
                # static variable — emit (y, x)
                # holds both coordinate arrays and the optional scalar time
                coords: dict[str, Any] = {"y": ys, "x": xs}
                if time is not None:
                    coords["time"] = time
                data_vars[name] = xr.DataArray(
                    arr.copy(),
                    dims=["y", "x"],
                    coords=coords,
                    attrs=attrs,
                )

        ds = xr.Dataset(data_vars, coords=base_coords)
        ds.attrs["Conventions"] = "CF-1.8"
        return ds

    @classmethod
    def from_xarray(cls, ds, nodata_value: float | int | None = None) -> "RasterBackend":
        """
        Build a ``RasterBackend`` from an ``xr.Dataset`` or ``xr.DataArray``.

        Variables with dimensions ``(y, x)`` are imported as static arrays.
        Variables with dimensions ``(time, y, x)`` are imported as temporal
        arrays with their time coordinates stored in ``self.time_coords``.

        Parameters
        ----------
        ds : xr.Dataset | xr.DataArray
        nodata_value : float | int | None

        Returns
        -------
        RasterBackend

        Raises
        ------
        ValueError
            If ``ds`` contains no spatial variables.
        """
        try:
            import xarray as xr
        except ImportError:
            raise ImportError(
                "xarray is required for RasterBackend.from_xarray(). "
                "Install it with: pip install xarray"
            )

        if isinstance(ds, xr.DataArray):
            name = ds.name or "data"
            ds = ds.to_dataset(name=name)

        spatial_vars = {
            name: var
            for name, var in ds.data_vars.items()
            if set(var.dims) >= {"y", "x"} and var.ndim in (2, 3)
        }

        if not spatial_vars:
            raise ValueError(
                "No spatial (y, x) or (time, y, x) variables found in Dataset."
            )

        # infer shape from first 2D variable, or spatial slice of first 3D
        shape_2d = None
        for var in spatial_vars.values():
            if var.ndim == 2:
                yi = var.dims.index("y")
                xi = var.dims.index("x")
                shape_2d = (var.shape[yi], var.shape[xi])
                break
        if shape_2d is None:
            var = next(iter(spatial_vars.values()))
            yi = var.dims.index("y")
            xi = var.dims.index("x")
            shape_2d = (var.shape[yi], var.shape[xi])

        rows, cols = shape_2d

        # recover transform
        transform = None
        try:
            import rasterio.transform
            ys = ds.coords["y"].values
            xs = ds.coords["x"].values
            if len(ys) >= 2 and len(xs) >= 2:
                res_y = float(ys[1] - ys[0])
                res_x = float(xs[1] - xs[0])
                origin_x = float(xs[0]) - res_x / 2
                origin_y = float(ys[0]) - res_y / 2
                transform = rasterio.transform.from_origin(
                    origin_x, origin_y - res_y * (rows - 1), res_x, abs(res_y)
                ) if res_y < 0 else rasterio.transform.Affine(
                    res_x, 0, origin_x, 0, res_y, origin_y
                )
        except Exception:
            pass

        # recover CRS
        crs = None
        if "spatial_ref" in ds.coords:
            try:
                from pyproj import CRS as ProjCRS
                wkt = ds.coords["spatial_ref"].attrs.get("crs_wkt", "")
                if wkt:
                    crs = ProjCRS.from_wkt(wkt)
            except Exception:
                pass

        backend = cls(
            shape=(rows, cols),
            nodata_value=nodata_value,
            transform=transform,
            crs=crs,
        )

        for name, var in spatial_vars.items():
            if var.ndim == 3 and "time" in var.dims:
                # temporal variable
                arr = var.transpose("time", "y", "x").values
                t   = ds.coords["time"].values
                backend.arrays[name]      = arr.copy()
                backend.time_coords[name] = t
            else:
                # static variable
                arr = var.transpose("y", "x").values
                backend.arrays[name] = arr.copy()

        return backend

    # ── spatial operations ────────────────────────────────────────────────────

    @staticmethod
    def shift2d(arr: np.ndarray, dr: int, dc: int) -> np.ndarray:
        """
        Shift ``arr`` by ``(dr, dc)`` rows/columns without wrap-around.
        Edges are filled with zero.

        Parameters
        ----------
        arr : np.ndarray  shape (y, x)
        dr : int
        dc : int

        Returns
        -------
        np.ndarray
        """
        rows, cols = arr.shape
        out = np.zeros_like(arr)
        rs  = slice(max(0, -dr), min(rows, rows - dr))
        rd  = slice(max(0,  dr), min(rows, rows + dr))
        cs_ = slice(max(0, -dc), min(cols, cols - dc))
        cd  = slice(max(0,  dc), min(cols, cols + dc))
        out[rd, cd] = arr[rs, cs_]
        return out

    def band_names(self) -> list[str]:
        """Return the names of all arrays currently stored in the backend."""
        return list(self.arrays.keys())

    def temporal_band_names(self) -> list[str]:
        """Return the names of temporal (time, y, x) arrays."""
        return list(self.time_coords.keys())

    def static_band_names(self) -> list[str]:
        """Return the names of static (y, x) arrays."""
        return [k for k in self.arrays if k not in self.time_coords]

    @staticmethod
    def neighbor_contact(
        condition: np.ndarray,
        neighborhood: list[tuple[int, int]] | None = None,
    ) -> np.ndarray:
        """
        Return a boolean mask where each cell has at least one neighbour
        satisfying ``condition``.

        Parameters
        ----------
        condition : np.ndarray  shape (y, x)
        neighborhood : list[tuple[int, int]] | None

        Returns
        -------
        np.ndarray  bool
        """
        if neighborhood is None:
            return binary_dilation(condition.astype(bool), structure=np.ones((3, 3)))
        result = np.zeros_like(condition, dtype=bool)
        for dr, dc in neighborhood:
            result |= RasterBackend.shift2d(condition.astype(np.int8), dr, dc) > 0
        return result

    def focal_sum(
        self,
        name: str,
        neighborhood: list[tuple[int, int]] = DIRS_MOORE,
    ) -> np.ndarray:
        """
        Focal sum across neighbours for a static (y, x) array.

        Parameters
        ----------
        name : str
        neighborhood : list[tuple[int, int]]

        Returns
        -------
        np.ndarray
        """
        arr    = self.arrays[name]
        if arr.ndim != 2:
            raise ValueError(
                f"focal_sum requires a static 2D array. "
                f"'{name}' has shape {arr.shape}. "
                f"Use get('{name}', time=t) to select a slice first."
            )
        result = np.zeros_like(arr, dtype=float)
        for dr, dc in neighborhood:
            result += self.shift2d(arr, dr, dc)
        return result

    def focal_sum_mask(
        self,
        mask: np.ndarray,
        neighborhood: list[tuple[int, int]] = DIRS_MOORE,
    ) -> np.ndarray:
        """
        Count neighbours where ``mask`` is ``True``.

        Parameters
        ----------
        mask : np.ndarray  shape (y, x)
        neighborhood : list[tuple[int, int]]

        Returns
        -------
        np.ndarray  int
        """
        result = np.zeros(self.shape, dtype=int)
        m = mask.astype(np.int8)
        for dr, dc in neighborhood:
            result += self.shift2d(m, dr, dc)
        return result

    # ── utilities ─────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        static   = [f"{k}:{v.dtype}{list(v.shape)}"
                    for k, v in self.arrays.items() if k not in self.time_coords]
        temporal = [f"{k}:{v.dtype}{list(v.shape)}@{list(self.time_coords[k])}"
                    for k, v in self.arrays.items() if k in self.time_coords]
        parts = static + temporal
        return f"RasterBackend(shape={self.shape}, arrays=[{', '.join(parts)}])"
