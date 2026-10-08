"""
tests/vector/test_vector_grid.py
====================================
Tests for vector_grid() and parse_idx() — vector grid utilities.
"""
from __future__ import annotations

import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon

from dissmodel.core import Environment
from dissmodel.geo.vector.vector_grid import vector_grid as vector_grid, parse_idx, GridPos


@pytest.fixture(autouse=True)
def default_env():
    return Environment(start_time=1, end_time=1)


# ══════════════════════════════════════════════════════════════════════════════
# vector_grid — return type and structure
# ══════════════════════════════════════════════════════════════════════════════

class TestReturnType:

    def test_returns_geodataframe(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1)
        assert isinstance(gdf, gpd.GeoDataFrame)

    def test_geometry_column_exists(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1)
        assert "geometry" in gdf.columns

    def test_geometries_are_polygons(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1)
        assert all(isinstance(g, Polygon) for g in gdf.geometry)


# ══════════════════════════════════════════════════════════════════════════════
# vector_grid — cell count
# ══════════════════════════════════════════════════════════════════════════════

class TestCellCount:

    @pytest.mark.parametrize("cols,rows,expected", [
        (3, 3, 9),
        (5, 5, 25),
        (10, 5, 50),
        (1, 1, 1),
        (1, 10, 10),
    ])
    def test_cell_count(self, cols, rows, expected):
        gdf = vector_grid(dimension=(cols, rows), resolution=1)
        assert len(gdf) == expected


# ══════════════════════════════════════════════════════════════════════════════
# vector_grid — index format
# ══════════════════════════════════════════════════════════════════════════════

class TestIndex:

    def test_index_format_is_two_numbers(self):
        """Index must follow 'a-b' format with two numeric parts."""
        gdf = vector_grid(dimension=(3, 3), resolution=1)
        for idx in gdf.index:
            parts = idx.split("-")
            assert len(parts) == 2
            assert parts[0].isdigit()
            assert parts[1].isdigit()

    def test_index_is_unique(self):
        gdf = vector_grid(dimension=(4, 4), resolution=1)
        assert gdf.index.is_unique

    def test_corner_indices_present(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1)
        assert "0-0" in gdf.index
        assert "0-2" in gdf.index
        assert "2-0" in gdf.index
        assert "2-2" in gdf.index


# ══════════════════════════════════════════════════════════════════════════════
# vector_grid — resolution
# ══════════════════════════════════════════════════════════════════════════════

class TestResolution:

    def test_cell_width_matches_resolution(self):
        res = 100
        gdf = vector_grid(dimension=(3, 3), resolution=res)
        b   = gdf.geometry.iloc[0].bounds   # (minx, miny, maxx, maxy)
        assert abs((b[2] - b[0]) - res) < 1e-6

    def test_cell_height_matches_resolution(self):
        res = 50
        gdf = vector_grid(dimension=(3, 3), resolution=res)
        b   = gdf.geometry.iloc[0].bounds
        assert abs((b[3] - b[1]) - res) < 1e-6

    def test_total_width(self):
        cols, res = 4, 10
        gdf   = vector_grid(dimension=(cols, 3), resolution=res)
        total = gdf.total_bounds[2] - gdf.total_bounds[0]
        assert abs(total - cols * res) < 1e-6

    def test_total_height(self):
        rows, res = 5, 10
        gdf   = vector_grid(dimension=(3, rows), resolution=res)
        total = gdf.total_bounds[3] - gdf.total_bounds[1]
        assert abs(total - rows * res) < 1e-6


# ══════════════════════════════════════════════════════════════════════════════
# vector_grid — attrs
# ══════════════════════════════════════════════════════════════════════════════

class TestAttrs:

    def test_single_attr_creates_column(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1, attrs={"state": 0})
        assert "state" in gdf.columns

    def test_attr_default_value(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1, attrs={"state": 7})
        assert (gdf["state"] == 7).all()

    def test_multiple_attrs(self):
        gdf = vector_grid(dimension=(3, 3), resolution=1,
                           attrs={"uso": 2, "alt": 0.0, "solo": 1})
        for col in ("uso", "alt", "solo"):
            assert col in gdf.columns

    def test_attrs_independent(self):
        """Writing one column must not affect another."""
        gdf = vector_grid(dimension=(3, 3), resolution=1,
                           attrs={"a": 0, "b": 0})
        gdf.loc["0-0", "a"] = 99
        assert gdf.loc["0-0", "a"] == 99
        assert gdf.loc["0-0", "b"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# parse_idx
# NOTE: parse_idx returns (col, row) — confirmed from implementation.
# ══════════════════════════════════════════════════════════════════════════════

class TestParseIdx:

    @pytest.mark.parametrize("idx,expected_row,expected_col", [
        ("0-0",   0,  0),
        ("1-2",   1,  2),
        ("10-5", 10,  5),
        ("0-99",  0, 99),
    ])
    def test_parses_correctly(self, idx, expected_row, expected_col):
        pos = parse_idx(idx)
        assert pos.row == expected_row
        assert pos.col == expected_col

    def test_returns_named_tuple(self):
        pos = parse_idx("3-7")
        assert hasattr(pos, "row") and hasattr(pos, "col")
        assert isinstance(pos.row, int) and isinstance(pos.col, int)

    def test_tuple_unpacking_still_works(self):
        """GridPos is a namedtuple — tuple unpacking must still work."""
        row, col = parse_idx("3-7")
        assert row == 3
        assert col == 7

    def test_consistent_with_grid_index(self):
        """parse_idx must round-trip: reconstructing the index gives the original."""
        gdf = vector_grid(dimension=(4, 3), resolution=1)
        for idx in gdf.index:
            pos = parse_idx(idx)
            assert f"{pos.row}-{pos.col}" == idx


# ── Vectorized construction must reproduce the original loop exactly ─────────

def _loop_reference(x_edges, y_edges, rx, ry):
    """The pre-vectorization implementation, kept as the reference."""
    from shapely.geometry import box

    cells, ids = [], []
    for i, x0 in enumerate(x_edges):
        for j, y0 in enumerate(y_edges):
            cells.append(box(x0, y0, x0 + rx, y0 + ry))
            ids.append(f"{j}-{i}")
    return cells, ids


@pytest.mark.parametrize(
    "kwargs, x_edges, y_edges, rx, ry",
    [
        (dict(dimension=(4, 3), resolution=1.0),
         np.arange(0, 4, 1.0), np.arange(0, 3, 1.0), 1.0, 1.0),
        (dict(bounds=(10.0, -5.0, 13.5, -1.0), resolution=0.5),
         np.arange(10.0, 13.5, 0.5), np.arange(-5.0, -1.0, 0.5), 0.5, 0.5),
        (dict(bounds=(0.0, 0.0, 10.0, 6.0), dimension=(5, 3)),
         np.arange(0.0, 10.0, 2.0), np.arange(0.0, 6.0, 2.0), 2.0, 2.0),
    ],
)
def test_vectorized_grid_identical_to_loop(kwargs, x_edges, y_edges, rx, ry):
    gdf = vector_grid(**kwargs)
    cells, ids = _loop_reference(x_edges, y_edges, rx, ry)

    assert list(gdf.index) == ids
    assert gdf.index.name == "id"
    for got, ref in zip(gdf.geometry, cells, strict=True):
        assert got.equals_exact(ref, 0.0)
        assert list(got.exterior.coords) == list(ref.exterior.coords)
