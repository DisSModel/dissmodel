"""
Compare two outputs (or the outputs of two ExperimentRecords).

The comparison is a ladder; each rung says something weaker than the one
above it, and the verdict is the strongest rung that holds:

1. ``bytes``     — the files are identical (SHA-256).
2. ``values``    — for rasters, the decoded bands are identical (shape, dtype
                   and values, SHA-256). This is what holds across machines
                   when only the GDAL build changed the encoding.
3. ``tolerance`` — only when the caller *declares* an absolute tolerance
                   (``atol``): every value differs by at most ``atol``.

The decoded values say nothing about *where* they are, so rasters also get a
``georef`` check (transform, CRS, nodata). A raster that moved, or changed
CRS or nodata, is ``differs`` whatever its values.

Verdicts: ``identical`` > ``values_identical`` > ``equivalent`` > ``differs``,
plus ``unverified`` when a rung that mattered could not be evaluated (file not
readable, rasterio missing, download failed). ``equivalent`` never appears
unless a tolerance was declared. A rung that could not be evaluated is
``None`` in ``levels``, never ``True``.

rasterio is optional; without it the comparison stops at ``bytes`` and the
result says so in ``values_error``.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from typing import TYPE_CHECKING, Callable

from dissmodel.io._utils import sha256_file

if TYPE_CHECKING:
    from dissmodel.executor.schemas import ExperimentRecord

GEOTIFF_SUFFIXES = (".tif", ".tiff")
OK_VERDICTS = ("identical", "values_identical", "equivalent")
ERROR_KEYS = ("bytes_error", "values_error", "georef_error", "fetch_error")


def _is_raster(*paths: str) -> bool:
    return all(p.lower().endswith(GEOTIFF_SUFFIXES) for p in paths)


def decoded_values_sha256(path: str) -> str:
    """SHA-256 over every band of a raster: shape, dtype and values."""
    import rasterio

    h = hashlib.sha256()
    with rasterio.open(path) as src:
        h.update(f"{src.count}x{src.height}x{src.width}".encode())
        for band in range(1, src.count + 1):
            data = src.read(band)
            h.update(str(data.dtype).encode())
            h.update(data.tobytes())
    return h.hexdigest()


def georef_matches(path_a: str, path_b: str) -> bool:
    """Same transform, CRS and nodata (CRS compared semantically, not as WKT text)."""
    import rasterio

    with rasterio.open(path_a) as a, rasterio.open(path_b) as b:
        return (
            a.transform == b.transform
            and a.crs == b.crs
            and a.nodatavals == b.nodatavals
        )


def max_abs_difference(path_a: str, path_b: str) -> float | None:
    """
    Largest absolute difference between two rasters, or ``None`` when they
    cannot be compared value by value (different shape or band count).
    NaNs in the same places are ignored; NaN in only one raster is ``inf``.
    """
    import numpy as np
    import rasterio

    worst = 0.0
    with rasterio.open(path_a) as a, rasterio.open(path_b) as b:
        if (a.count, a.height, a.width) != (b.count, b.height, b.width):
            return None
        for band in range(1, a.count + 1):
            x = a.read(band).astype("float64")
            y = b.read(band).astype("float64")
            nan_x, nan_y = np.isnan(x), np.isnan(y)
            if (nan_x != nan_y).any():
                return float("inf")
            keep = ~nan_x
            if keep.any():
                worst = max(worst, float(np.abs(x[keep] - y[keep]).max()))
    return worst


def compare_files(
    path_a: str,
    path_b: str,
    atol: float | None = None,
    *,
    bytes_a: str | None = None,
    bytes_b: str | None = None,
) -> dict:
    """
    Compare two local files. ``bytes_a``/``bytes_b`` are known SHA-256 values
    (e.g. from a record's ``artifacts["output"]``); they are computed from the
    files when not given.
    """
    levels: dict = {"bytes": None, "values": None, "georef": None, "tolerance": None}
    result: dict = {"levels": levels, "atol": atol}

    try:
        sa = bytes_a or sha256_file(path_a)
        sb = bytes_b or sha256_file(path_b)
        levels["bytes"] = sa == sb
    except OSError as exc:
        result["bytes_error"] = str(exc)

    if levels["bytes"] is True:
        if _is_raster(path_a, path_b):
            # Identical files have identical decoded values and georeference.
            levels["values"] = levels["georef"] = True
    elif _is_raster(path_a, path_b):
        try:
            ha, hb = decoded_values_sha256(path_a), decoded_values_sha256(path_b)
            levels["values"] = ha == hb
            result["values_sha256"] = hb
            levels["georef"] = georef_matches(path_a, path_b)
            if levels["values"] is False and atol is not None and levels["georef"]:
                diff = max_abs_difference(path_a, path_b)
                result["max_abs_diff"] = diff
                levels["tolerance"] = diff is not None and diff <= atol
        except Exception as exc:  # noqa: BLE001 — reported, never fatal
            result["values_error"] = f"{type(exc).__name__}: {exc}"

    result["verdict"] = _verdict(levels, result)
    # Keys kept from the 0.6 platform so existing clients keep working.
    result["file_identical"] = levels["bytes"]
    result["values_identical"] = levels["values"]
    return result


def _verdict(levels: dict, result: dict) -> str:
    if levels["bytes"] is True:
        return "identical"
    if levels["georef"] is False:
        return "differs"
    if levels["values"] is True:
        return "values_identical"
    if levels["tolerance"] is True:
        return "equivalent"
    if any(k in result for k in ERROR_KEYS):
        return "unverified"      # something that mattered could not be checked
    return "differs"


def compare_outputs(
    original: "ExperimentRecord",
    reproduction: "ExperimentRecord",
    atol: float | None = None,
    local_copy: Callable[[str, str], str] | None = None,
) -> dict:
    """
    Compare the ``output`` artifact of two records.

    ``local_copy(uri, workdir)`` must return a readable local path for a
    remote URI (the platform passes its s3:// downloader); by default URIs
    are used as local paths.
    """
    fetch = local_copy or (lambda uri, _workdir: uri)
    a_path, b_path = original.output_path or "", reproduction.output_path or ""
    sha_a, sha_b = original.artifacts.get("output"), reproduction.artifacts.get("output")

    if sha_a and sha_a == sha_b:
        # Same recorded checksum: identical, no need to fetch anything.
        raster = _is_raster(a_path, b_path) or None   # None where it makes no sense
        result = {"levels": {"bytes": True, "values": raster, "georef": raster, "tolerance": None},
                  "atol": atol, "verdict": "identical",
                  "file_identical": True, "values_identical": raster}
    else:
        with tempfile.TemporaryDirectory() as workdir:
            try:
                pa, pb = fetch(a_path, workdir), fetch(b_path, workdir)
            except Exception as exc:  # noqa: BLE001
                bytes_level = (sha_a == sha_b) if (sha_a and sha_b) else None
                levels = {"bytes": bytes_level, "values": None, "georef": None, "tolerance": None}
                result = {"levels": levels, "atol": atol,
                          "fetch_error": f"{type(exc).__name__}: {exc}"}
                result["verdict"] = _verdict(levels, result)
                result["file_identical"], result["values_identical"] = bytes_level, None
            else:
                result = compare_files(pa, pb, atol, bytes_a=sha_a, bytes_b=sha_b)
    result["of"] = original.experiment_id
    result["original_output"] = original.output_path
    result["environment"] = {
        "original":     original.metrics.get("environment"),
        "reproduction": reproduction.metrics.get("environment"),
    }
    return result


def summary(result: dict) -> str:
    def word(v):
        return {True: "identical", False: "DIFFERS", None: "not checked"}[v]

    lv = result["levels"]
    text = (
        f"{result.get('of', '')}: {result['verdict']} "
        f"(bytes {word(lv['bytes'])}, decoded values {word(lv['values'])}, "
        f"georeference {word(lv.get('georef'))}"
    )
    if result.get("atol") is not None:
        text += f", tolerance {result['atol']:g} {word(lv['tolerance'])}"
        if result.get("max_abs_diff") is not None:
            text += f", max |diff| {result['max_abs_diff']:.3g}"
    return text + ")"
