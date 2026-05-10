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
    Stored in ``self.arrays`` as ``np.ndarray`` of shape ``(rows, cols)``.
    No names are reserved — domain models define their own
    (``"uso"``, ``"alt"``, ``"solo"``, ``"state"``, ``"temperature"``, …).

    Parameters
    ----------
    shape : tuple[int, int]
        Grid shape as ``(rows, cols)``.
    nodata_value : float | int | None
        Sentinel value used to mark cells outside the study extent.
        When provided, ``nodata_mask`` derives the extent mask automatically,
        so ``RasterMap`` renders those cells as transparent without any extra
        configuration. Default: ``None``.

    Examples
    --------
    >>> b = RasterBackend(shape=(10, 10))
    >>> b.set("state", np.zeros((10, 10), dtype=np.int8))
    >>> b.get("state").shape
    (10, 10)

    >>> b = RasterBackend(shape=(10, 10), nodata_value=-1)
    >>> b.nodata_mask   # True = valid cell, False = outside extent
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
        self.nodata_value = nodata_value   # sentinel for out-of-extent cells

        self.transform    = transform
        self.crs          = crs

    # ── extent mask ───────────────────────────────────────────────────────────

    @property
    def nodata_mask(self) -> np.ndarray | None:
        """
        Boolean mask: ``True`` = valid cell, ``False`` = outside extent / nodata.

        Derived in priority order:
        1. ``arrays["mask"]``  — explicit mask band (dissluc / coastal convention:
                                 non-zero = valid).
        2. ``nodata_value``    — applied over the first available array.
        3. ``None``            — no information; ``RasterMap`` skips auto-masking.

        Used by ``RasterMap`` (``auto_mask=True``) to render out-of-extent pixels
        as transparent without any per-project configuration.
        """
        if "mask" in self.arrays:
            return self.arrays["mask"] != 0

        if self.nodata_value is not None and self.arrays:
            first = next(iter(self.arrays.values()))
            return first != self.nodata_value

        return None

    # ── read / write ──────────────────────────────────────────────────────────

    def set(self, name: str, array: np.ndarray) -> None:
        """Store a copy of ``array`` under ``name``."""
        self.arrays[name] = np.asarray(array).copy()

    def get(self, name: str) -> np.ndarray:
        """
        Return a direct reference to the named array.

        Use ``.copy()`` to obtain a snapshot equivalent to TerraME's ``.past``.

        Raises
        ------
        KeyError
            If ``name`` is not in ``self.arrays``.
        """
        return self.arrays[name]

    def snapshot(self) -> dict[str, np.ndarray]:
        """
        Return a deep copy of all arrays — equivalent to TerraME's ``.past`` mechanism.

        Typical usage::

            past     = backend.snapshot()
            uso_past = past["uso"]   # state at the beginning of the step

        Returns
        -------
        dict[str, np.ndarray]
            Dictionary mapping array names to independent copies.
        """
        return {k: v.copy() for k, v in self.arrays.items()}

    def rename_band(self, old: str, new: str) -> None:
        """
        Rename an array in-place. No-op if ``old`` does not exist.

        Parameters
        ----------
        old : str
            Current band name.
        new : str
            Target band name.
        """
        if old in self.arrays:
            self.arrays[new] = self.arrays.pop(old)

    # ── xarray interoperability ───────────────────────────────────────────────

    def to_xarray(self, time: int | None = None):
        """
        Convert the backend to an ``xr.Dataset``.

        Each array in ``self.arrays`` becomes a ``DataVariable`` with
        dimensions ``(y, x)``. If ``time`` is given, a scalar ``time``
        coordinate is added — useful when assembling multi-step outputs.

        Spatial coordinates are derived from ``self.transform`` when available
        (rasterio Affine), following the Pangeo convention of cell centres.
        When ``transform`` is ``None`` (e.g. backends rasterized from vector),
        integer pixel indices are used instead.

        CRS is stored as a ``spatial_ref`` coordinate (CF convention) when
        ``self.crs`` is set and ``pyproj`` is available.

        Parameters
        ----------
        time : int | None
            Optional simulation step to attach as a scalar ``time`` coordinate.

        Returns
        -------
        xr.Dataset

        Raises
        ------
        ImportError
            If ``xarray`` is not installed.

        Examples
        --------
        >>> ds = backend.to_xarray()
        >>> ds["uso"].dims
        ('y', 'x')

        >>> ds = backend.to_xarray(time=42)
        >>> ds.coords["time"].item()
        42
        """
        try:
            import xarray as xr
        except ImportError:
            raise ImportError(
                "xarray is required for RasterBackend.to_xarray(). "
                "Install it with: pip install xarray"
            )

        rows, cols = self.shape

        # spatial coordinates — cell centres from Affine transform or pixel indices
        if self.transform is not None:
            try:
                # rasterio Affine: transform * (col + 0.5, row + 0.5) = centre
                xs = np.array([self.transform.c + (c + 0.5) * self.transform.a
                                for c in range(cols)])
                ys = np.array([self.transform.f + (r + 0.5) * self.transform.e
                                for r in range(rows)])
            except AttributeError:
                # transform present but not rasterio Affine — fall back to indices
                xs = np.arange(cols, dtype=float)
                ys = np.arange(rows, dtype=float)
        else:
            xs = np.arange(cols, dtype=float)
            ys = np.arange(rows, dtype=float)

        coords: dict = {"y": ys, "x": xs}

        if time is not None:
            coords["time"] = time

        # CRS as spatial_ref coordinate (CF / rioxarray convention)
        if self.crs is not None:
            try:
                from pyproj import CRS as ProjCRS
                crs_obj = ProjCRS.from_user_input(self.crs)
                coords["spatial_ref"] = xr.DataArray(
                    0,
                    attrs={
                        "crs_wkt":       crs_obj.to_wkt(),
                        "grid_mapping":  "spatial_ref",
                    },
                )
            except Exception:
                # pyproj unavailable or CRS unresolvable — skip spatial_ref
                pass

        data_vars = {}
        for name, arr in self.arrays.items():
            attrs: dict = {}
            if self.nodata_value is not None:
                attrs["_FillValue"] = self.nodata_value
            if self.crs is not None and "spatial_ref" in coords:
                attrs["grid_mapping"] = "spatial_ref"

            data_vars[name] = xr.DataArray(
                arr.copy(),
                dims=["y", "x"],
                coords={"y": ys, "x": xs},
                attrs=attrs,
            )

        ds = xr.Dataset(data_vars, coords=coords)
        ds.attrs["Conventions"] = "CF-1.8"
        return ds

    @classmethod
    def from_xarray(cls, ds, nodata_value: float | int | None = None) -> "RasterBackend":
        """
        Build a ``RasterBackend`` from an ``xr.Dataset`` or ``xr.DataArray``.

        All variables with exactly two dimensions ``(y, x)`` (in any order)
        are imported as arrays. Variables with other dimensionality
        (e.g. ``spatial_ref`` scalars) are silently skipped.

        CRS is recovered from the ``spatial_ref`` coordinate (CF convention)
        when present and ``pyproj`` is available.

        Parameters
        ----------
        ds : xr.Dataset | xr.DataArray
            Source dataset. A ``DataArray`` is wrapped into a single-variable
            ``Dataset`` using ``da.name`` (falling back to ``"data"``).
        nodata_value : float | int | None
            Forwarded to the new backend's ``nodata_value``. Default: ``None``.

        Returns
        -------
        RasterBackend

        Raises
        ------
        ImportError
            If ``xarray`` is not installed.
        ValueError
            If ``ds`` contains no variables with ``(y, x)`` dimensions.

        Examples
        --------
        >>> backend2 = RasterBackend.from_xarray(ds)
        >>> np.array_equal(backend2.get("uso"), backend.get("uso"))
        True
        """
        try:
            import xarray as xr
        except ImportError:
            raise ImportError(
                "xarray is required for RasterBackend.from_xarray(). "
                "Install it with: pip install xarray"
            )

        # normalise DataArray → Dataset
        if isinstance(ds, xr.DataArray):
            name = ds.name or "data"
            ds = ds.to_dataset(name=name)

        # collect 2D (y, x) variables — skip scalars and non-spatial vars
        spatial_vars = {
            name: var
            for name, var in ds.data_vars.items()
            if set(var.dims) >= {"y", "x"} and var.ndim == 2
        }

        if not spatial_vars:
            raise ValueError(
                "No 2D (y, x) variables found in the Dataset. "
                "Ensure dimensions are named 'y' and 'x'."
            )

        # infer shape from first variable
        first_var = next(iter(spatial_vars.values()))
        y_idx = first_var.dims.index("y")
        x_idx = first_var.dims.index("x")
        rows = first_var.shape[y_idx]
        cols = first_var.shape[x_idx]

        # recover transform from y/x coords if they look like spatial coords
        transform = None
        try:
            import rasterio.transform
            ys = ds.coords["y"].values
            xs = ds.coords["x"].values
            if len(ys) >= 2 and len(xs) >= 2:
                # reconstruct Affine from cell-centre coordinates
                res_y = float(ys[1] - ys[0])   # negative for north-up
                res_x = float(xs[1] - xs[0])
                origin_x = float(xs[0]) - res_x / 2
                origin_y = float(ys[0]) - res_y / 2
                # rasterio.transform.from_origin expects (west, north, xsize, ysize)
                # origin_y is already the north edge if res_y < 0
                transform = rasterio.transform.from_origin(
                    origin_x, origin_y, res_x, abs(res_y)
                )
        except Exception:
            pass  # transform recovery is best-effort

        # recover CRS from spatial_ref coordinate (CF convention)
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
            # transpose to (y, x) canonical order before storing
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
        arr : np.ndarray
        dr : int
            Row offset (positive = down, negative = up).
        dc : int
            Column offset (positive = right, negative = left).

        Returns
        -------
        np.ndarray
            Shifted array of the same shape as ``arr``.
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
        condition : np.ndarray
        neighborhood : list[tuple[int, int]] | None
            ``None`` uses Moore neighbourhood via ``binary_dilation``.

        Returns
        -------
        np.ndarray
            Boolean array.
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
        Focal sum: for each cell, sum the values of ``name`` across its neighbours.
        The cell itself is not included.

        Parameters
        ----------
        name : str
        neighborhood : list[tuple[int, int]]
            Default: ``DIRS_MOORE``.

        Returns
        -------
        np.ndarray
        """
        arr    = self.arrays[name]
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
        mask : np.ndarray
        neighborhood : list[tuple[int, int]]
            Default: ``DIRS_MOORE``.

        Returns
        -------
        np.ndarray
            Integer array with per-cell neighbour counts.
        """
        result = np.zeros(self.shape, dtype=int)
        m = mask.astype(np.int8)
        for dr, dc in neighborhood:
            result += self.shift2d(m, dr, dc)
        return result

    # ── utilities ─────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        bands = ", ".join(
            f"{k}:{v.dtype}[{v.shape}]" for k, v in self.arrays.items()
        )
        return f"RasterBackend(shape={self.shape}, arrays=[{bands}])"
