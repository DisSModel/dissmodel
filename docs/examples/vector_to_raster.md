# Loading Vector Data into the Raster Substrate

DisSModel can load any vector file (Shapefile, GeoJSON, GeoPackage, or a
`.zip` containing a shapefile) and convert it directly into a
`RasterBackend`, so raster models can run on real geographic data without
intermediate GIS steps.

## How it works

```
vector file → GeoDataFrame → rasterize → NumPy arrays → RasterBackend → raster model
```

The rasterization step (powered by `rasterio.features.rasterize`) runs
once; after that the model runs entirely on NumPy arrays.

!!! note "Grid regularity"
    This workflow is most accurate when the input already contains a
    **regular grid** of equal-area polygons (e.g. 100×100 m cells), the
    typical output of spatial homogenization tools. For irregular polygons
    (municipalities, watersheds), cell values are burned by centroid or by
    touch — inspect the result before running long simulations.

---

## `vector_to_raster_backend`

```python
from dissmodel.io.convert import vector_to_raster_backend

b = vector_to_raster_backend(
    source     = "data/mangue_grid.shp",   # path, .zip, or a GeoDataFrame
    resolution = 100,                      # 100 m cells
    attrs      = ["uso", "alt", "solo"],
    crs        = "EPSG:31984",             # reproject if needed
)

print(b.shape)             # (rows, cols) from bounding box + resolution
print(b.band_names())      # ['mask', 'uso', 'alt', 'solo']
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | `str`, `Path` or `GeoDataFrame` | Vector file or in-memory GeoDataFrame |
| `resolution` | `float` | Cell size in CRS units (metres for a metric CRS) |
| `attrs` | `list[str]` or `dict[str, default]` | Columns to rasterize |
| `crs` | `str`, `int`, or `None` | Target CRS — reprojects if needed |
| `all_touched` | `bool` | Burn all touched cells (default: centre only) |
| `nodata` | `int` or `float` | Fill value for uncovered cells (default: `0`) |
| `add_mask` | `bool` | Add a `"mask"` band marking covered cells (default: `True`) |

To set per-column defaults for uncovered cells, pass a dict:

```python
b = vector_to_raster_backend(
    source     = "data/mangue_grid.shp",
    resolution = 100,
    attrs      = {"uso": 5, "alt": 0.0, "solo": 1},
    crs        = "EPSG:31984",
)
```

`shapefile_to_raster_backend` is a deprecated alias of this function and
emits a `FutureWarning`.

---

## Full example — raster model from a vector file

```python
from dissmodel.core import Environment
from dissmodel.io.convert import vector_to_raster_backend
from dissmodel.visualization.raster_map import RasterMap

# your own RasterModel subclass, e.g. the BR-MANGUE flood model
from myproject.flood import FloodRasterModel

# 1. vector file → RasterBackend
b = vector_to_raster_backend(
    source     = "data/mangue_grid.shp",
    resolution = 100,
    attrs      = {"uso": 5, "alt": 0.0, "solo": 1},
    crs        = "EPSG:31984",
)
print(f"Grid: {b.shape[0]} rows × {b.shape[1]} cols = {b.shape[0] * b.shape[1]:,} cells")

# 2. run the raster model
env = Environment(start_time=2012, end_time=2100)
FloodRasterModel(backend=b, taxa=0.011)
RasterMap(backend=b, band="uso", title="Land Use")
env.run()
```

---

## Saving results to GeoTIFF

`vector_to_raster_backend` stores the CRS and affine transform on the
backend, so `save_geotiff` writes a georeferenced file without extra
arguments:

```python
from dissmodel.io.raster import save_geotiff

checksum = save_geotiff(b, "output/flood_result.tif")   # returns SHA-256
```

---

## Same data, two substrates

```python
# ── vector substrate ─────────────────────────────────────────────────────────
import geopandas as gpd

gdf = gpd.read_file("data/mangue_grid.shp").to_crs("EPSG:31984")
# → GeoDataFrame with real geometries; use with SpatialModel / CellularAutomaton

# ── raster substrate ─────────────────────────────────────────────────────────
from dissmodel.io.convert import vector_to_raster_backend

b = vector_to_raster_backend(
    "data/mangue_grid.shp", resolution=100,
    attrs=["uso", "alt", "solo"], crs="EPSG:31984",
)
# → RasterBackend with the same attributes; use with RasterModel
```

The data source is the same file; only the substrate changes. For measured
run times of the two substrates on the same model, see the benchmarks in
`benchmarks/` and the `brmangue-dissmodel` benchmark executor.

---

## API Reference

::: dissmodel.io.convert.vector_to_raster_backend

::: dissmodel.io.raster.save_geotiff
