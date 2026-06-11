from __future__ import annotations

# Xarray I/O — integração com ecossistema PyData (NetCDF, Zarr, rioxarray).
#
# Design notes:
# - Dimensions follow Pangeo conventions: (y, x) for snapshots, (time, y, x) future
# - CRS: stored as spatial_ref coordinate (CF-1.8 convention), compatible with rioxarray
# - Storage: NetCDF local via to_netcdf / open_dataset; Zarr/MinIO planned for BDC (v0.2)
# - Conversion lives in RasterBackend.to_xarray() / from_xarray() — these are thin wrappers
#
# Usage:
#   ds, checksum = load_xarray("path/to/data.nc")
#   checksum     = save_xarray(backend, "path/to/output.nc", step=42)
#
# Post-MVP (v0.2): DataSource.type = "bdc_stac" | "wcpms" via Intake catalog


def load_xarray(uri: str, minio_client=None, **kwargs):
    """
    Load a NetCDF or Zarr file into a ``RasterBackend``.

    Reads the file as an ``xr.Dataset`` and delegates to
    ``RasterBackend.from_xarray()``. CRS and transform are recovered
    from the ``spatial_ref`` coordinate when present (CF-1.8 convention).

    Parameters
    ----------
    uri : str
        Local path or ``s3://`` URI.
        - Local ``.nc`` / ``.nc4``: read via ``xr.open_dataset``
        - ``.zarr`` or ``s3://``: read via ``xr.open_zarr`` (requires ``zarr``)
    minio_client : optional
        Not used for local paths. Reserved for future MinIO/S3 integration.
    **kwargs
        Forwarded to ``xr.open_dataset`` or ``xr.open_zarr``.

    Returns
    -------
    tuple[RasterBackend, str]
        ``(backend, checksum)`` — checksum is SHA-256 hex of the file bytes
        for local paths; empty string for remote URIs (computed post-download
        in future versions).

    Raises
    ------
    ImportError
        If ``xarray`` is not installed.
    FileNotFoundError
        If ``uri`` is a local path that does not exist.

    Examples
    --------
    ```python
    backend, checksum = load_xarray("simulation_step_42.nc")
    backend.band_names()  # ['uso', 'alt', 'solo']
    ```
    """
    try:
        import xarray as xr
    except ImportError:
        raise ImportError(
            "xarray is required for load_xarray(). "
            "Install it with: pip install xarray"
        )

    from dissmodel.geo.raster.backend import RasterBackend

    is_zarr = uri.endswith(".zarr") or uri.startswith("s3://")

    if is_zarr:
        ds = xr.open_zarr(uri, **kwargs)
        checksum = ""  # remote — checksum computed post-download (future)
    else:
        ds = xr.open_dataset(uri, **kwargs)
        checksum = _file_checksum(uri)

    backend = RasterBackend.from_xarray(ds)
    return backend, checksum


def save_xarray(
    backend_or_dataset,
    uri: str,
    step: int | None = None,
    minio_client=None,
    **kwargs,
) -> str:
    """
    Save a ``RasterBackend`` (or ``xr.Dataset``) to NetCDF or Zarr.

    When given a ``RasterBackend``, delegates to ``backend.to_xarray(time=step)``
    before saving. The ``step`` parameter attaches the simulation step as a
    scalar ``time`` coordinate — useful for labelling output snapshots.

    Parameters
    ----------
    backend_or_dataset : RasterBackend | xr.Dataset
        Source data.
    uri : str
        Output path.
        - ``.nc`` / ``.nc4``: written via ``ds.to_netcdf()`` (local)
        - ``.zarr`` or ``s3://``: written via ``ds.to_zarr()`` (requires ``zarr``)
    step : int | None
        Simulation step to attach as ``time`` coordinate. Default: ``None``.
    minio_client : optional
        Reserved for future MinIO/S3 integration.
    **kwargs
        Forwarded to ``ds.to_netcdf()`` or ``ds.to_zarr()``.

    Returns
    -------
    str
        SHA-256 checksum of the written file (local paths only).
        Empty string for remote URIs (future).

    Raises
    ------
    ImportError
        If ``xarray`` is not installed.

    Examples
    --------
    ```python
    # backend: a RasterBackend (e.g. from load_xarray or vector_to_raster_backend)
    checksum = save_xarray(backend, "output_step_42.nc", step=42)

    # save as Zarr (requires zarr package)
    checksum = save_xarray(backend, "output.zarr", step=42)
    ```
    """
    try:
        import xarray  # noqa: F401 — availability check; used via to_xarray()
    except ImportError:
        raise ImportError(
            "xarray is required for save_xarray(). "
            "Install it with: pip install xarray"
        )

    from dissmodel.geo.raster.backend import RasterBackend

    if isinstance(backend_or_dataset, RasterBackend):
        ds = backend_or_dataset.to_xarray(time=step)
    else:
        ds = backend_or_dataset

    is_zarr = uri.endswith(".zarr") or uri.startswith("s3://")

    if is_zarr:
        ds.to_zarr(uri, **kwargs)
        return ""  # remote checksum: future
    else:
        ds.to_netcdf(uri, **kwargs)
        return _file_checksum(uri)


# ── internal helpers ──────────────────────────────────────────────────────────

def _file_checksum(path: str) -> str:
    """SHA-256 hex digest of a local file. Returns '' if file not found."""
    import hashlib
    import pathlib
    try:
        data = pathlib.Path(path).read_bytes()
        return hashlib.sha256(data).hexdigest()
    except FileNotFoundError:
        return ""
