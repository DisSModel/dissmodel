from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Protocol, Union

import geopandas as gpd
from libpysal.weights import W


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class WeightStrategy(Protocol):
    """
    Protocol defining the expected contract for a libpysal neighborhood strategy.

    Any class that implements ``from_dataframe`` satisfies this protocol
    structurally, without requiring explicit inheritance.

    Examples
    --------
    >>> from libpysal.weights import Queen, Rook
    >>> # Queen and Rook satisfy WeightStrategy automatically
    """

    @classmethod
    def from_dataframe(cls, gdf: gpd.GeoDataFrame, **kwargs: Any) -> W:
        ...


# Reusable type alias — import this in other modules instead of redefining it
StrategyType = Optional[WeightStrategy]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _resolve_neighbors_dict(
    neighbors_dict: Optional[Union[dict[Any, list[Any]], str]],
) -> Optional[dict[Any, list[Any]]]:
    """
    Resolve ``neighbors_dict`` to a plain dict, loading from JSON if needed.

    Parameters
    ----------
    neighbors_dict : dict, str, or None
        A precomputed mapping, a path to a JSON file, or ``None``.

    Returns
    -------
    dict or None
        Resolved dict, or ``None`` if the input was ``None``.

    Raises
    ------
    FileNotFoundError
        If a string path is provided but the file does not exist.
    ValueError
        If the value is not a dict, ``None``, or a valid JSON file path.
    """
    if neighbors_dict is None:
        return None
    if isinstance(neighbors_dict, dict):
        return neighbors_dict
    if isinstance(neighbors_dict, str):
        path = Path(neighbors_dict)
        if not path.is_file():
            raise FileNotFoundError(
                f"Neighborhood file not found: {neighbors_dict}"
            )
        with open(path) as f:
            return json.load(f)
    raise ValueError(
        "`neighbors_dict` must be a dictionary or a path to a JSON file."
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def attach_neighbors(
    gdf: gpd.GeoDataFrame,
    strategy: StrategyType = None,
    neighbors_dict: Optional[dict[Any, list[Any]] | str] = None,
    **kwargs: Any,
) -> gpd.GeoDataFrame:
    """
    Attach a neighborhood structure to a GeoDataFrame.

    Adds a ``'_neighs'`` column containing the list of neighbor indices for
    each cell. Mutates and returns the same GeoDataFrame.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame whose cells will receive the neighborhood column.
    strategy : WeightStrategy, optional
        Libpysal weight class (e.g. ``Queen``, ``Rook``) whose
        ``from_dataframe`` classmethod will be called. Ignored if
        ``neighbors_dict`` is provided.
    neighbors_dict : dict or str, optional
        Precomputed neighborhood. Accepted formats:

        - ``dict`` — ``{index: [neighbor_indices]}`` mapping.
        - ``str`` — path to a JSON file with the same structure.
        - ``None`` — neighborhood will be computed via ``strategy``.
    **kwargs :
        Extra keyword arguments forwarded to ``strategy.from_dataframe``.

    Returns
    -------
    geopandas.GeoDataFrame
        The same ``gdf`` with the ``'_neighs'`` column added.

    Raises
    ------
    FileNotFoundError
        If a string path is provided in ``neighbors_dict`` but does not exist.
    ValueError
        If ``neighbors_dict`` is not a dict, ``None``, or a valid JSON path.
    ValueError
        If neither ``strategy`` nor ``neighbors_dict`` is provided.

    Examples
    --------
    ```python
    from libpysal.weights import Queen

    # gdf: an existing GeoDataFrame (e.g. from vector_grid or read_file)
    gdf = attach_neighbors(gdf, strategy=Queen)
    gdf = attach_neighbors(gdf, neighbors_dict="neighborhood.json")
    gdf = attach_neighbors(gdf, strategy=Queen, ids="cell_id")
    ```
    """
    resolved = _resolve_neighbors_dict(neighbors_dict)

    w: W
    if resolved is not None:
        w = W(resolved)
    elif strategy is not None:
         if "use_index" not in kwargs:
            kwargs["use_index"] = True
         w = strategy.from_dataframe(gdf, **kwargs)
    else:
        raise ValueError("Provide either `strategy` or `neighbors_dict`.")

    gdf["_neighs"] = gdf.index.map(lambda idx: w.neighbors.get(idx, []))
    return gdf


def get_neighbors(gdf: gpd.GeoDataFrame, idx: Any) -> list[Any]:
    """
    Return the neighbor indices for a specific cell.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame with the ``'_neighs'`` column already populated.
    idx : any
        Index of the cell of interest.

    Returns
    -------
    list
        List of neighbor indices. Returns an empty list if no neighbors exist.

    Raises
    ------
    ValueError
        If the ``'_neighs'`` column is not present.
    KeyError
        If ``idx`` does not exist in the GeoDataFrame.

    Examples
    --------
    ```python
    # gdf: a GeoDataFrame with a "_neighs" column from attach_neighbors()
    get_neighbors(gdf, "10-5")  # ['9-5', '11-5', '10-4', '10-6']
    ```
    """
    if "_neighs" not in gdf.columns:
        raise ValueError(
            "Column '_neighs' not found. Run `attach_neighbors` first."
        )
    if idx not in gdf.index:
        raise KeyError(f"Index '{idx}' not found in the GeoDataFrame.")
    return gdf.at[idx, "_neighs"]


def get_neighbor_values(
    gdf: gpd.GeoDataFrame,
    idx: Any,
    attr: str,
) -> list[Any]:
    """
    Return the values of an attribute for all neighbors of a cell.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame with the ``'_neighs'`` column already populated.
    idx : any
        Index of the cell of interest.
    attr : str
        Name of the attribute column to retrieve.

    Returns
    -------
    list
        Attribute values for the neighbors, in the same order as ``'_neighs'``.

    Raises
    ------
    ValueError
        If the ``'_neighs'`` column is not present.
    KeyError
        If ``idx`` or ``attr`` does not exist in the GeoDataFrame.

    Examples
    --------
    ```python
    # gdf: a GeoDataFrame with a "_neighs" column from attach_neighbors()
    get_neighbor_values(gdf, "10-5", "land_use")  # [1, 1, 2, 1]
    ```
    """
    neighbors = get_neighbors(gdf, idx)
    if attr not in gdf.columns:
        raise KeyError(f"Attribute '{attr}' not found in the GeoDataFrame.")
    return gdf.loc[neighbors, attr].tolist()


def export_neighbors(gdf: gpd.GeoDataFrame, path: str) -> None:
    """
    Export the neighborhood structure of a GeoDataFrame to a JSON file.

    Useful for persisting computed neighborhoods and reusing them via
    ``attach_neighbors(gdf, neighbors_dict='neighborhood.json')``.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        GeoDataFrame with the ``'_neighs'`` column already populated.
    path : str
        Destination JSON file path.

    Raises
    ------
    ValueError
        If the ``'_neighs'`` column is not present.

    Examples
    --------
    ```python
    # gdf: a GeoDataFrame with a "_neighs" column from attach_neighbors()
    export_neighbors(gdf, "neighborhood.json")
    ```
    """
    if "_neighs" not in gdf.columns:
        raise ValueError(
            "Column '_neighs' not found. Run `attach_neighbors` first."
        )
    neighbors_dict = gdf["_neighs"].to_dict()
    with open(path, "w") as f:
        json.dump(neighbors_dict, f, indent=2)


__all__ = [
    "WeightStrategy",
    "StrategyType",
    "attach_neighbors",
    "get_neighbors",
    "get_neighbor_values",
    "export_neighbors",
]