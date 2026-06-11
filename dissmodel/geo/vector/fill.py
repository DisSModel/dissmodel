from __future__ import annotations

import random
from enum import Enum
from typing import Any, Callable, Optional, Union

import geopandas as gpd
import numpy as np
from affine import Affine
from rasterstats import zonal_stats


# ---------------------------------------------------------------------------
# Strategy enum
# ---------------------------------------------------------------------------

class FillStrategy(str, Enum):
    """
    Available fill strategies for populating GeoDataFrame attributes.

    Attributes
    ----------
    ZONAL_STATS : str
        Fill cells with statistics extracted from a raster.
    MIN_DISTANCE : str
        Fill cells with the minimum distance to a target GeoDataFrame.
    RANDOM_SAMPLE : str
        Fill cells with random samples drawn from a distribution.
    PATTERN : str
        Fill cells using a 2-D pattern matrix.

    Examples
    --------
    >>> FillStrategy.RANDOM_SAMPLE
    <FillStrategy.RANDOM_SAMPLE: 'random_sample'>
    >>> FillStrategy("pattern")
    <FillStrategy.PATTERN: 'pattern'>
    """

    ZONAL_STATS = "zonal_stats"
    MIN_DISTANCE = "min_distance"
    RANDOM_SAMPLE = "random_sample"
    PATTERN = "pattern"


# ---------------------------------------------------------------------------
# Internal registry
# ---------------------------------------------------------------------------

_fill_strategies: dict[FillStrategy, Callable[..., Any]] = {}


def register_strategy(
    name: FillStrategy,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Register a fill strategy under the given name.

    Parameters
    ----------
    name : FillStrategy
        Key under which the strategy will be registered.

    Returns
    -------
    Callable
        Decorator that registers and returns the decorated function.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        _fill_strategies[name] = func
        return func
    return decorator


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_SampleData = Union[list[Any], dict[str, Any]]


def _generate_sample(data: _SampleData, size: int = 1) -> list[Any]:
    """
    Draw random samples from ``data``.

    Parameters
    ----------
    data : list or dict
        Sampling source. Accepted formats:

        - ``list`` — uniform random choice among items.
        - ``{"min": int, "max": int}`` — uniform integer range.
        - ``{option: weight, ...}`` — weighted random choice.

    size : int, optional
        Number of samples to draw, by default 1.

    Returns
    -------
    list
        List of sampled values.

    Raises
    ------
    ValueError
        If ``data`` is not a list or dict.

    Examples
    --------
    >>> import random; random.seed(0)
    >>> _generate_sample([1, 2, 3], size=3)
    [3, 3, 2]
    >>> _generate_sample({"min": 0, "max": 1}, size=2)
    [1, 1]
    """
    if isinstance(data, dict):
        if "min" in data and "max" in data:
            return [random.randint(data["min"], data["max"]) for _ in range(size)]
        options = list(data.keys())
        weights = list(data.values())
        return random.choices(options, weights=weights, k=size)

    if isinstance(data, list):
        return random.choices(data, k=size)

    raise ValueError("`data` must be a list or a dictionary.")


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

@register_strategy(FillStrategy.PATTERN)
def _fill_pattern(
    gdf: gpd.GeoDataFrame,
    attr: str,
    pattern: list[list[Any]],
    start_x: int = 0,
    start_y: int = 0,
) -> None:
    """
    Fill a GeoDataFrame attribute using a 2-D pattern matrix.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame whose cells will be filled.
    attr : str
        Name of the attribute column to fill.
    pattern : list of list
        2-D matrix representing the pattern to apply.
        ``pattern[row][col]`` maps to cell ``'row-col'`` in the grid.
    start_x : int, optional
        Column offset (x direction), by default 0.
    start_y : int, optional
        Row offset (y direction), by default 0.

    Notes
    -----
    Cell IDs follow the ``'row-col'`` (``y-x``) convention used by
    :func:`~dissmodel.geo.vector_grid.vector_grid` and
    :func:`~dissmodel.geo.vector_grid.parse_idx`.
    """
    n_rows = len(pattern)
    n_cols = len(pattern[0]) if n_rows > 0 else 0
    for row in range(n_rows):
        for col in range(n_cols):
            idx = f"{start_y + row}-{start_x + col}"  
            if idx in gdf.index:
                gdf.loc[idx, attr] = pattern[n_rows - row - 1][col]

@register_strategy(FillStrategy.RANDOM_SAMPLE)
def _fill_random_sample(
    gdf: gpd.GeoDataFrame,
    attr: str,
    data: _SampleData,
    seed: Optional[int] = None,
) -> None:
    """
    Fill a GeoDataFrame attribute with random samples drawn from ``data``.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame to fill.
    attr : str
        Name of the attribute column to fill.
    data : list or dict
        Sampling source — see :func:`_generate_sample` for accepted formats.
    seed : int, optional
        Random seed for reproducibility, by default ``None``.
    """
    if seed is not None:
        random.seed(seed)
    gdf[attr] = _generate_sample(data, size=len(gdf))


@register_strategy(FillStrategy.ZONAL_STATS)
def _fill_zonal_stats(
    vectors: gpd.GeoDataFrame,
    raster_data: np.ndarray,
    affine: Affine,
    stats: list[str],
    prefix: str = "attr_",
    nodata: float = -999,
) -> None:
    """
    Fill a GeoDataFrame with zonal statistics computed from a raster.

    Parameters
    ----------
    vectors : geopandas.GeoDataFrame
        GeoDataFrame with the zones.
    raster_data : numpy.ndarray
        2-D array with raster values.
    affine : affine.Affine
        Affine transform of the raster (origin and resolution).
    stats : list of str
        Statistics to compute, e.g. ``["mean", "sum", "min", "max"]``.
    prefix : str, optional
        Column name prefix for each statistic, by default ``"attr_"``.
    nodata : float, optional
        Value in the raster to treat as no-data, by default ``-999``.
    """
    stats_output: list[dict[str, Any]] = zonal_stats(
        vectors, raster_data, affine=affine, nodata=nodata, stats=stats
    )
    for stat in stats:
        vectors[f"{prefix}{stat}"] = [row[stat] for row in stats_output]


@register_strategy(FillStrategy.MIN_DISTANCE)
def _fill_min_distance(
    from_gdf: gpd.GeoDataFrame,
    to_gdf: gpd.GeoDataFrame,
    attr_name: str = "min_distance",
) -> None:
    """
    Fill each row in ``from_gdf`` with the minimum distance to any geometry
    in ``to_gdf``.

    For results in metres, use a projected CRS (e.g. UTM) on both
    GeoDataFrames.

    Parameters
    ----------
    from_gdf : geopandas.GeoDataFrame
        GeoDataFrame whose rows will be annotated.
    to_gdf : geopandas.GeoDataFrame
        GeoDataFrame used as the distance target.
    attr_name : str, optional
        Name of the column to store the distances, by default
        ``"min_distance"``.
    """
    from_gdf[attr_name] = from_gdf.geometry.apply(
        lambda geom: to_gdf.geometry.distance(geom).min()
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def fill(strategy: FillStrategy | str, **kwargs: Any) -> Any:
    """
    Execute a fill strategy by name.

    Parameters
    ----------
    strategy : FillStrategy or str
        Strategy to execute. Accepted values: ``'pattern'``,
        ``'random_sample'``, ``'zonal_stats'``, ``'min_distance'``.
    **kwargs :
        Arguments forwarded to the chosen strategy function.

    Returns
    -------
    Any
        Whatever the strategy function returns. Most strategies mutate the
        GeoDataFrame in place and return ``None``.

    Raises
    ------
    ValueError
        If ``strategy`` is not a registered :class:`FillStrategy` value.

    Examples
    --------
    ```python
    # grid, roads: existing GeoDataFrames (e.g. from vector_grid / read_file)
    fill(FillStrategy.RANDOM_SAMPLE, gdf=grid, attr="state",
         data=[0, 1], seed=42)
    fill("min_distance", from_gdf=grid, to_gdf=roads,
         attr_name="dist_road")
    fill(FillStrategy.PATTERN, gdf=grid, attr="zone",
         pattern=[[1, 2], [3, 4]])
    ```
    """
    key = FillStrategy(strategy)
    if key not in _fill_strategies:
        raise ValueError(f"Unknown strategy: {strategy!r}")
    return _fill_strategies[key](**kwargs)


__all__ = ["fill", "FillStrategy", "register_strategy"]
