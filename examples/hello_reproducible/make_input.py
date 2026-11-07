# make_input.py
from dissmodel.geo import raster_grid
from dissmodel.io import save_dataset

grid = raster_grid(rows=100, cols=100, attrs={"state": 0})   # 0 = forest
grid.arrays["state"][50, 50] = 1                             # 1 = burning
save_dataset(grid, "forest.tif")
