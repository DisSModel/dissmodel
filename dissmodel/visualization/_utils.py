from __future__ import annotations

import matplotlib


def _detect_environment() -> str:
    """
    Detecta o ambiente de execução atual.

    Returns
    -------
    'colab'   — Google Colab
    'jupyter' — Jupyter Notebook / JupyterLab local
    'ipython' — IPython terminal (não notebook)
    'headless'— sem IPython (CI, scripts, terminal puro)
    """
    import sys
    if "google.colab" in sys.modules:
        return "colab"
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is None:
            return "headless"
        shell = ip.__class__.__name__
        if shell == "ZMQInteractiveShell":
            return "jupyter"
        if shell == "TerminalInteractiveShell":
            return "ipython"
        return "headless"
    except ImportError:
        return "headless"


# avaliado uma vez no import — sem overhead nos execute()
_ENV = _detect_environment()

# habilita widgets customizados no Colab (ipyleaflet, ipywidgets, etc.)
# deve acontecer antes de qualquer display() — no-op fora do Colab
if _ENV == "colab":
    try:
        from google.colab import output as _colab_output
        _colab_output.enable_custom_widget_manager()
    except Exception:  # noqa: BLE001, S110 — Colab-only setup; no-op everywhere else
        pass


def is_notebook() -> bool:
    """True se estiver em Jupyter Notebook/Lab ou Google Colab."""
    return _ENV in ("jupyter", "colab")


def is_interactive_backend() -> bool:
    """
    True se o backend matplotlib suporta janelas interativas.

    Nota: 'agg' é headless e foi removido desta lista intencionalmente —
    estava causando detecção incorreta no Colab (que roda com backend agg).
    """
    backend = matplotlib.get_backend().lower()
    interactive_backends = {
        "qt5agg", "qtagg", "qt4agg", "tkagg",
        "macosx", "gtk3agg", "gtk4agg", "wxagg",
    }
    return backend in interactive_backends
