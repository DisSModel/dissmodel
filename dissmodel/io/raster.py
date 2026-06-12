# dissmodel/io/raster.py
from __future__ import annotations

import io
import os
import pathlib
import shutil
import tempfile
import zipfile

import numpy as np

from dissmodel.io._utils import resolve_uri, sha256_bytes
from dissmodel.geo.raster.backend import RasterBackend

try:
    import rasterio
    import rasterio.features
    import rasterio.transform
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


# ── GeoTIFF → RasterBackend ───────────────────────────────────────────────────

def load_geotiff(
    uri:          str,
    minio_client = None,
    band_spec:   list[tuple[str, str, float]] | None = None,
    **kwargs,
) -> tuple[tuple[RasterBackend, dict], str]:
    """
    Load a GeoTIFF into a RasterBackend from any URI.

    Supports local path, s3://, http(s)://, and .zip archives.
    Returns ((backend, meta), sha256_checksum).

    Parameters
    ----------
    uri : str
        Source URI. Accepts local path, s3://bucket/key, http(s)://, or
        a .zip archive containing a single GeoTIFF.
    minio_client : Minio or None
        Optional MinIO client. If None, uses the default client from
        environment variables.
    band_spec : list of (name, dtype, nodata) or None
        Mapping from band index to array name and dtype.
        If None, all bands are loaded using their tag names.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio is required — pip install rasterio")

    content, checksum = resolve_uri(uri, minio_client)

    suffix = ".zip" if uri.rstrip("/").endswith(".zip") else ".tif"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name

    try:
        backend, meta = _read_geotiff(tmp, band_spec)
    finally:
        os.unlink(tmp)

    return (backend, meta), checksum


def _read_geotiff(
    path: str,
    band_spec: list[tuple[str, str, float]] | None,
) -> tuple[RasterBackend, dict]:
    """Read a local GeoTIFF (plain or zipped) into a RasterBackend."""
    path_str = str(path)

    if path_str.endswith(".zip"):
        with zipfile.ZipFile(path_str) as z:
            tif_name = next(f for f in z.namelist() if f.endswith(".tif"))
        path_str = f"zip://{path_str}!{tif_name}"

    with rasterio.open(path_str) as ds:
        rows, cols = ds.height, ds.width
        backend    = RasterBackend(shape=(rows, cols))

        if band_spec:
            for i, (name, dtype, nodata) in enumerate(band_spec, start=1):
                if i > ds.count:
                    break
                arr = ds.read(i).astype(dtype)
                if np.all(arr == nodata):
                    continue   # skip uninitialised bands
                backend.arrays[name] = arr
        else:
            # Load all bands using their tag names or positional names
            for i in range(1, ds.count + 1):
                tags = ds.tags(i)
                name = tags.get("name", f"band_{i}")
                backend.arrays[name] = ds.read(i)

        meta = {
            "transform": ds.transform,
            "crs":       ds.crs,
            "tags":      ds.tags(),
        }

    return backend, meta


# ── RasterBackend → GeoTIFF ───────────────────────────────────────────────────

def save_geotiff(
    data,
    uri:          str,
    minio_client = None,
    band_spec:   list[tuple[str, str, float]] | None = None,
    crs          = None,
    transform    = None,
    compress:    str = "deflate",
    **kwargs,
) -> str:
    """
    Save a RasterBackend as GeoTIFF to any URI.

    Supports local path and s3://.
    Returns sha256 checksum of the saved file.

    Parameters
    ----------
    data : (RasterBackend, dict)
        Backend and metadata dict (as returned by load_geotiff).
    uri : str
        Destination URI. Local path or s3://bucket/key.
    band_spec : list of (name, dtype, nodata) or None
        Bands to write in order. Missing bands are filled with nodata.
        If None, all arrays in the backend are written.
    crs : str or None
        CRS string (e.g. "EPSG:31984"). Overrides meta["crs"].
    transform : Affine or None
        Affine geotransform. Overrides meta["transform"].
    compress : str
        Compression algorithm. Default: "deflate".

    Notes
    -----
    GeoTIFF stores a single dtype per file. When band dtypes differ
    (e.g. an int32 categorical band alongside a float32 continuous band),
    all bands are promoted to their common NumPy result type
    (``np.result_type``) before writing.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio is required — pip install rasterio")

    backend, meta = data
    resolved_crs       = crs       or (meta.get("crs") if meta else None)
    resolved_transform = transform or (meta.get("transform") if meta else None)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        tmp = f.name

    try:
        _write_geotiff(
            backend, tmp,
            band_spec = band_spec,
            crs       = resolved_crs,
            transform = resolved_transform,
            compress  = compress,
        )

        with open(tmp, "rb") as f:
            content = f.read()

        if uri.startswith("s3://"):
            if minio_client is None:
                from dissmodel.io._storage import get_default_client
                minio_client = get_default_client()
            bucket, key = uri[5:].split("/", 1)
            minio_client.put_object(
                bucket_name  = bucket,
                object_name  = key,
                data         = io.BytesIO(content),
                length       = len(content),
                content_type = "image/tiff",
            )
        else:
            pathlib.Path(uri).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(tmp, uri)

    finally:
        os.unlink(tmp)

    return sha256_bytes(content)


def _write_geotiff(
    backend:   RasterBackend,
    path:      str,
    band_spec: list[tuple[str, str, float]] | None,
    crs,
    transform,
    compress:  str = "deflate",
) -> None:
    """Write a RasterBackend to a local GeoTIFF file."""
    rows, cols = backend.shape

    if band_spec:
        arrays = []
        for name, dtype, nodata in band_spec:
            arr = backend.arrays.get(
                name,
                np.full((rows, cols), nodata, dtype=dtype),
            )
            arrays.append(arr.astype(dtype))
        names = [name for name, _, _ in band_spec]
    else:
        # Write all arrays preserving their individual dtypes
        names  = list(backend.arrays.keys())
        arrays = [backend.arrays[n] for n in names]

    if transform is None:
        transform = rasterio.transform.from_bounds(0, 0, cols, rows, cols, rows)

    # GeoTIFF requires a single dtype for all bands. When bands have mixed
    # dtypes (e.g. int32 categorical + float32 continuous), promote every
    # band to the common NumPy result type instead of silently truncating
    # to the first band's dtype.
    dtypes = {arr.dtype for arr in arrays}
    if len(dtypes) > 1:
        common = np.result_type(*dtypes)
        arrays = [arr.astype(common) for arr in arrays]

    with rasterio.open(
        path, "w",
        driver    = "GTiff",
        height    = rows,
        width     = cols,
        count     = len(arrays),
        dtype     = str(arrays[0].dtype),
        crs       = crs,
        transform = transform,
        compress  = compress,
    ) as dst:
        for i, (arr, name) in enumerate(zip(arrays, names), start=1):
            dst.write(arr, i)
            dst.update_tags(i, name=name)