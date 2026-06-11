# CLI Examples

Runnable command-line examples live in the satellite repositories
[dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) (cellular automata)
and [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn)
(system dynamics), not in this repository.

Install the model libraries:

```bash
pip install "git+https://github.com/DisSModel/dissmodel-ca.git"
pip install "git+https://github.com/DisSModel/dissmodel-sysdyn.git"
```

To run the example scripts, clone the repository that hosts them:

| Example | Repository | Run (from a clone of the repo) |
|:---|:---|:---|
| Game of Life (vector) | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | `python examples/cli/ca_game_of_life.py` |
| Game of Life (raster) | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | `python examples/cli/ca_game_of_life_raster.py` |
| SIR epidemiological model | [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn) | `python examples/cli/sysdyn_sir.py` |

Each repository's own README documents its full example set and
parameters.
