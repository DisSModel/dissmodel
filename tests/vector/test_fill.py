"""
tests/vector/test_fill.py
====================================
Tests for fill() and FillStrategy — vector grid fill utilities.
"""
import pytest
from dissmodel.core import Environment
from dissmodel.geo import vector_grid, fill, FillStrategy
from dissmodel.geo.vector.vector_grid import parse_idx


@pytest.fixture(autouse=True)
def default_env():
    return Environment(start_time=1, end_time=1)


def test_pattern_square_grid():
    """Pattern applied to correct cells on a square grid."""
    gdf = vector_grid(dimension=(3, 3), resolution=1.0, attrs={"state": 0})
    pattern = [[1, 0], [0, 1]]
    fill(FillStrategy.PATTERN, gdf=gdf, attr="state", pattern=pattern)
    # pattern[1][0] → row=0, col=0 → idx "0-0"
    assert gdf.loc["0-0", "state"] == 0
    # pattern[0][0] → row=1, col=0 → idx "1-0"
    assert gdf.loc["1-0", "state"] == 1


def test_pattern_nonsquare_grid():
    """Pattern applied to correct cells on a non-square grid (3 cols x 5 rows)."""
    gdf = vector_grid(dimension=(3, 5), resolution=1.0, attrs={"state": 0})
    assert len(gdf) == 15

    pattern = [[1, 1, 1]]  # 1 row, 3 cols
    fill(FillStrategy.PATTERN, gdf=gdf, attr="state", pattern=pattern,
         start_x=0, start_y=0)

    # pattern[0][0..2] → row=0, col=0,1,2 → idx "0-0", "0-1", "0-2"
    assert gdf.loc["0-0", "state"] == 1
    assert gdf.loc["0-1", "state"] == 1
    assert gdf.loc["0-2", "state"] == 1
    # Other rows untouched
    assert gdf.loc["1-0", "state"] == 0


def test_pattern_out_of_bounds_ignored():
    """Pattern cells outside the grid are silently ignored."""
    gdf = vector_grid(dimension=(2, 2), resolution=1.0, attrs={"state": 0})
    pattern = [[1, 1, 1], [1, 1, 1]]  # wider than grid
    fill(FillStrategy.PATTERN, gdf=gdf, attr="state", pattern=pattern)
    # No KeyError should be raised
    assert gdf.loc["0-0", "state"] == 1
    assert gdf.loc["0-1", "state"] == 1


def test_parse_idx_roundtrip():
    """parse_idx correctly extracts col, row from row-col index string."""
    pos = parse_idx("3-4")
    assert pos.row == 3
    assert pos.col == 4


# ---------------------------------------------------------------------------
# MIN_DISTANCE — spatial-index implementation must equal the brute force
# ---------------------------------------------------------------------------

def _brute_force_min_distance(from_gdf, to_gdf):
    return from_gdf.geometry.apply(lambda g: to_gdf.geometry.distance(g).min()).to_numpy()


def _targets(kind, rng, n):
    import geopandas as gpd
    from shapely.geometry import LineString, Point, box

    if kind == "points":
        geoms = [Point(*rng.random(2) * 20) for _ in range(n)]
    elif kind == "lines":
        geoms = [LineString(rng.random((3, 2)) * 20) for _ in range(n)]
    else:
        geoms = []
        for _ in range(n):
            x, y = rng.random(2) * 18
            geoms.append(box(x, y, x + 1.5, y + 1.5))
    return gpd.GeoDataFrame(geometry=geoms)


@pytest.mark.parametrize("kind", ["points", "lines", "polygons"])
def test_min_distance_matches_brute_force(kind):
    import numpy as np

    rng = np.random.default_rng(42)
    grid = vector_grid(dimension=(20, 20), resolution=1.0)
    targets = _targets(kind, rng, 25)
    expected = _brute_force_min_distance(grid, targets)

    fill(FillStrategy.MIN_DISTANCE, from_gdf=grid, to_gdf=targets, attr_name="d")

    np.testing.assert_array_equal(grid["d"].to_numpy(), expected)
    # cells overlapped by a target are at distance zero
    if kind == "polygons":
        assert (grid["d"] == 0).any()


def test_min_distance_keeps_index_and_row_order():
    import geopandas as gpd
    from shapely.geometry import Point

    grid = vector_grid(dimension=(4, 3), resolution=1.0)
    shuffled = grid.sample(frac=1.0, random_state=0)
    targets = gpd.GeoDataFrame(geometry=[Point(0, 0)])
    fill(FillStrategy.MIN_DISTANCE, from_gdf=shuffled, to_gdf=targets)

    assert list(shuffled.index) == list(grid.sample(frac=1.0, random_state=0).index)
    for idx, row in shuffled.iterrows():
        assert row["min_distance"] == row.geometry.distance(Point(0, 0))


def test_min_distance_empty_target_gives_nan():
    import geopandas as gpd

    grid = vector_grid(dimension=(3, 3), resolution=1.0)
    fill(FillStrategy.MIN_DISTANCE, from_gdf=grid, to_gdf=gpd.GeoDataFrame(geometry=[]))
    assert grid["min_distance"].isna().all()


def test_min_distance_missing_geometry_gives_nan():
    import geopandas as gpd
    import numpy as np
    from shapely.geometry import Point

    grid = vector_grid(dimension=(3, 1), resolution=1.0)
    grid.loc[grid.index[1], "geometry"] = None
    targets = gpd.GeoDataFrame(geometry=[Point(-1, 0.5)])
    fill(FillStrategy.MIN_DISTANCE, from_gdf=grid, to_gdf=targets)

    values = grid["min_distance"].to_numpy()
    assert values[0] == 1.0 and values[2] == 3.0   # cells span x in [0,1] and [2,3]
    assert np.isnan(values[1])


def test_min_distance_warns_on_crs_mismatch():
    import geopandas as gpd
    from shapely.geometry import Point

    grid = vector_grid(dimension=(2, 2), resolution=1.0, crs="EPSG:31984")
    targets = gpd.GeoDataFrame(geometry=[Point(0, 0)], crs="EPSG:4326")
    with pytest.warns(UserWarning, match="CRS mismatch"):
        fill(FillStrategy.MIN_DISTANCE, from_gdf=grid, to_gdf=targets)
