#!/usr/bin/env bash
# Hello, reproducible: run a model, check the record, repeat the run, see a difference.
# Needs dissmodel >= 0.7 and rasterio. Run it from this folder: bash run.sh
set -eu

python make_input.py                                   # forest.tif: a forest with one fire

python my_executor.py run --input forest.tif --output result.tif \
                          --toml model.toml --preserve-output-name

dissmodel verify result.record.json                    # is the output the one in the record?
dissmodel reproduce result.record.json --module my_executor   # run it again: identical?

python my_executor.py run --input forest.tif --output other.tif \
                          --toml model.toml --param prob_spread=0.5 --preserve-output-name

# A different parameter gives a different output, so compare exits with status 1.
dissmodel compare result.tif other.tif || echo "(exit status $?: the outputs differ, as expected)"
