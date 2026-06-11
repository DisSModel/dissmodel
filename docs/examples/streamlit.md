# Streamlit Examples

Interactive Streamlit dashboards live in the satellite repositories
[dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) (cellular automata)
and [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn)
(system dynamics), not in this repository.

Clone the hosting repository and run any app with
`streamlit run examples/streamlit/<filename>.py`:

| App | Repository | Description |
|:---|:---|:---|
| `ca_all.py` | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | All cellular automata models — dynamic selector |
| `ca_game_of_life.py` | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | Game of Life |
| `ca_fire_model.py` | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | Forest fire spread |
| `ca_fire_model_prob.py` | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | Probabilistic fire with regrowth |
| `ca_snow.py` | [dissmodel-ca](https://github.com/DisSModel/dissmodel-ca) | Snowfall and accumulation |
| `sysdyn_all.py` | [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn) | All system dynamics models — dynamic selector |
| `sysdyn_sir.py` | [dissmodel-sysdyn](https://github.com/DisSModel/dissmodel-sysdyn) | SIR epidemiological model |

For example:

```bash
git clone https://github.com/DisSModel/dissmodel-ca.git
cd dissmodel-ca
pip install . streamlit
streamlit run examples/streamlit/ca_all.py
```
