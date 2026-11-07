# Hello, reproducible

A forest fire (a small cellular automaton) taken from a script to a
reproducible experiment, in five commands. The full walkthrough, with the
output of each step, is in
[Getting started](https://dissmodel.github.io/dissmodel/getting_started/#your-first-reproducible-experiment).

| File | What it is |
|---|---|
| `forest_fire_model.py` | the model: science only, no file reading or writing |
| `my_executor.py` | the executor: reads the input, runs, writes the output and the record |
| `make_input.py` | creates `forest.tif`, a 100 x 100 forest with one fire |
| `model.toml` | the parameters, including the seed |
| `run.sh` | all the commands, in order |

**Start with the input.** `forest.tif` does not exist until you create it.

```bash
pip install "dissmodel>=0.7" rasterio
python make_input.py            # 1. creates forest.tif (a 100 x 100 forest with one fire)
bash run.sh                     # 2. runs everything else, in order (it also calls make_input.py)
```

Or one command at a time, from this folder:

```bash
python make_input.py
python my_executor.py run --input forest.tif --output result.tif --toml model.toml
dissmodel verify result_<id>.record.json        # <id> is the short ID in the file names
```

`FileNotFoundError: 'forest.tif'` means `make_input.py` has not run yet. `run.sh`
adds `--preserve-output-name`, so the files are called `result.tif` and
`result.record.json` and the commands do not need the ID.

The experiment ID in the file names (`<id>`) is generated at each run, so it
will not be the same as in the walkthrough, nor will the timings. The hash of a
GeoTIFF can also differ between machines (it depends on the GDAL build). None
of that means something went wrong.

You should see `matches the record`, then `identical` for the reproduction,
then `differs` for the run with another `prob_spread`.

These files are the ones shown in the walkthrough, and
`tests/examples/test_hello_reproducible.py` runs them and checks that the
walkthrough has not drifted from them.
