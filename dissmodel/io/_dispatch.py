from __future__ import annotations

from dissmodel.io._utils import detect_format


def load_dataset(uri: str, minio_client=None, fmt: str | None = None, **kwargs):
    """
    Load any supported dataset from a URI.

    Format is inferred from the URI extension unless fmt is provided.

    Supported formats
    -----------------
    vector  — .shp, .gpkg, .geojson, .zip (shapefile inside zip)
    raster  — .tif, .tiff
    xarray  — .zarr, .nc  (post-MVP — BDC/STAC integration)

    Returns
    -------
    (data, sha256_checksum)
    """
    resolved_fmt = fmt or detect_format(uri)

    if resolved_fmt == "vector":
        from dissmodel.io.vector import load_gdf
        return load_gdf(uri, minio_client=minio_client, **kwargs)

    if resolved_fmt == "raster":
        from dissmodel.io.raster import load_geotiff
        return load_geotiff(uri, minio_client=minio_client, **kwargs)

    if resolved_fmt == "xarray":
        from dissmodel.io._xarray import load_xarray
        return load_xarray(uri, minio_client=minio_client, **kwargs)

    raise ValueError(f"Unsupported format: '{resolved_fmt}'")


def _check_data_matches_format(data, uri: str, fmt: str) -> None:
    """
    Fail early, with a readable message, when the data type cannot be
    written to the format chosen by the URI (e.g. a GeoDataFrame to .tif).
    Without this the writer fails deep inside with an AttributeError.
    """
    import geopandas as gpd

    from dissmodel.geo.raster.backend import RasterBackend

    backend = data[0] if isinstance(data, tuple) and data else data
    if fmt == "raster" and isinstance(data, gpd.GeoDataFrame):
        raise TypeError(
            f"Cannot save a GeoDataFrame to raster path '{uri}'. Use a vector "
            "extension (.gpkg, .shp, .geojson); for the CLI, pass --output "
            "with that extension or set `output_suffix = \".gpkg\"` on the "
            "executor class."
        )
    if fmt == "vector" and isinstance(backend, RasterBackend):
        raise TypeError(
            f"Cannot save a RasterBackend to vector path '{uri}'. Use a raster "
            "extension (.tif); for the CLI, pass --output with that extension "
            "or set `output_suffix = \".tif\"` on the executor class."
        )


def save_dataset(data, uri: str, minio_client=None, fmt: str | None = None, **kwargs) -> str:
    """
    Save any supported dataset to a URI.

    Format is inferred from the URI extension unless fmt is provided.

    Returns
    -------
    sha256_checksum of the saved file
    """
    resolved_fmt = fmt or detect_format(uri)
    _check_data_matches_format(data, uri, resolved_fmt)

    if resolved_fmt == "vector":
        from dissmodel.io.vector import save_gdf
        return save_gdf(data, uri, minio_client=minio_client, **kwargs)

    if resolved_fmt == "raster":
        from dissmodel.io.raster import save_geotiff
        return save_geotiff(data, uri, minio_client=minio_client, **kwargs)

    if resolved_fmt == "xarray":
        from dissmodel.io._xarray import save_xarray
        return save_xarray(data, uri, minio_client=minio_client, **kwargs)

    raise ValueError(f"Unsupported format: '{resolved_fmt}'")
