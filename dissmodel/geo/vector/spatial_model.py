"""
dissmodel/geo/spatial_model.py
================================
Classe base para modelos com suporte a GeoDataFrame e vizinhança.

Responsabilidade
----------------
Prover infraestrutura espacial — gdf, criação de vizinhança, acesso a
vizinhos — sem impor nenhum contrato de regra de transição.

Hierarquia
----------
    Model  (dissmodel.core)
      └── SpatialModel          ← este arquivo
            ├── CellularAutomaton  gdf + rule(idx) por célula (pull)
            └── (modelos livres)   gdf + execute() orientado a fonte (push)

Por que separar
---------------
CellularAutomaton.rule(idx) assume que cada célula calcula seu próprio
novo estado de forma independente (modelo pull). Modelos orientados a
FONTE — como o Hidro do BR-MANGUE — modificam vizinhos a partir da
fonte (modelo push). Eles precisam da infraestrutura espacial mas não
podem usar o contrato de rule().

SpatialModel fornece:
    - self.gdf                   GeoDataFrame compartilhado
    - create_neighborhood()      constrói _neighs via libpysal ou dict
    - neighs_id(idx)             lista de índices vizinhos (cache)
    - neighs(idx)                GeoDataFrame dos vizinhos
    - neighbor_values(idx, col)  array numpy dos valores vizinhos

Uso
---
    class MeuModelo(SpatialModel):
        def __init__(self, gdf, meu_param=1.0, **kwargs):
            super().__init__(gdf, **kwargs)
            self.meu_param = meu_param
            self.create_neighborhood()

        def execute(self):
            nivel = self.env.now() * self.meu_param
            # lógica livre — orientada a fonte, por grupo, etc.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np
import geopandas as gpd
from libpysal.weights import Queen

from dissmodel.core import Model
# import from the defining module (not the dissmodel.geo package) to avoid
# a circular import while dissmodel.geo.__init__ is still initializing
from dissmodel.geo.vector.neighborhood import StrategyType, attach_neighbors


class SpatialModel(Model):
    """
    Model com suporte a GeoDataFrame e vizinhança.

    Subclasse de Model que acrescenta infraestrutura espacial sem impor
    contrato de regra de transição. Pode ser herdada diretamente por
    modelos com execute() livre (push/fonte) ou indiretamente via
    CellularAutomaton (pull/rule).

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Grade ou polígonos da simulação.
    step : float, optional
        Time increment per execution step, by default 1.
    start_time : float, optional
        Simulation start time, by default 0.
    end_time : float, optional
        Simulation end time, by default ``math.inf``.
    name : str, optional
        Optional model name, by default ``""``.
    **kwargs :
        Extra keyword arguments forwarded to :class:`~dissmodel.core.Model`.
    """

    def __init__(
        self,
        gdf: gpd.GeoDataFrame,
        step: float = 1,
        start_time: float = 0,
        end_time: float = math.inf,
        name: str = "",
        **kwargs: Any,
    ) -> None:
        self.gdf: gpd.GeoDataFrame       = gdf
        self._neighborhood_created: bool = False
        self._neighs_cache: dict         = {}
        super().__init__(
            step=step,
            start_time=start_time,
            end_time=end_time,
            name=name,
            **kwargs,
        )

    # ── vizinhança ────────────────────────────────────────────────────────────

    def create_neighborhood(
        self,
        strategy: StrategyType = Queen,
        neighbors_dict: Optional[dict | str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Constrói e anexa a estrutura de vizinhança ao GeoDataFrame.

        Popula ``gdf["_neighs"]`` com a lista de índices vizinhos por célula.

        Parameters
        ----------
        strategy : type, optional
            Libpysal weight class (e.g. ``Queen``, ``Rook``),
            by default ``Queen``.
        neighbors_dict : dict or str, optional
            Precomputed ``{id: [neighbor_ids]}`` mapping or a path to a JSON
            file with the same structure. If provided, ``strategy`` is ignored.
        **kwargs :
            Extra keyword arguments forwarded to the strategy.
        """
        self.gdf = attach_neighbors(
            gdf=self.gdf,
            strategy=strategy,
            neighbors_dict=neighbors_dict,
            **kwargs,
        )
        self._neighborhood_created = True
        self._neighs_cache = self.gdf["_neighs"].to_dict()

    def neighs_id(self, idx: Any) -> list[Any]:
        """
        Return the neighbor indices for cell ``idx``.

        Parameters
        ----------
        idx : any
            Index of the cell in the GeoDataFrame.

        Returns
        -------
        list
            List of neighbor indices.
        """
        if self._neighs_cache:
            return self._neighs_cache.get(idx, [])
        return self.gdf.loc[idx, "_neighs"]

    def neighs(self, idx: Any) -> gpd.GeoDataFrame:
        """
        Return the neighboring cells of ``idx`` as a GeoDataFrame.

        Parameters
        ----------
        idx : any
            Index of the cell in the GeoDataFrame.

        Returns
        -------
        geopandas.GeoDataFrame
            GeoDataFrame containing the neighboring rows.

        Raises
        ------
        RuntimeError
            If the neighborhood has not been created yet.
        """
        if not self._neighborhood_created:
            raise RuntimeError(
                "Neighborhood has not been created yet. "
                "Call `.create_neighborhood()` first."
            )
        return self.gdf.loc[self.neighs_id(idx)]

    def neighbor_values(self, idx: Any, col: str) -> np.ndarray:
        """
        Return the values of ``col`` for all neighbors of cell ``idx``.

        Faster than ``neighs(idx)[col]`` because it skips geometry overhead.

        Parameters
        ----------
        idx : any
            Index of the cell in the GeoDataFrame.
        col : str
            Column name to retrieve.

        Returns
        -------
        numpy.ndarray
            Array of neighbor values.
        """
        return self.gdf.loc[self.neighs_id(idx), col].values
