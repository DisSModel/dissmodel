"""Pacote dissmodel - modelagem espacial discreta"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dissmodel")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"
