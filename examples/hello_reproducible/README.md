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

```bash
pip install "dissmodel>=0.7" rasterio
bash run.sh
```

You should see `matches the record`, then `identical` for the reproduction,
then `differs` for the run with another `prob_spread`.

These files are the ones shown in the walkthrough, and
`tests/examples/test_hello_reproducible.py` runs them and checks that the
walkthrough has not drifted from them.
