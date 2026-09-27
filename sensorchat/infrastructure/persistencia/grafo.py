import logging
from pathlib import Path

import numpy as np

from ...domain.grafo import GrafoConceitos
from .arquivos import gravar_json, ler_json

log = logging.getLogger(__name__)


class RepositorioGrafoEmArquivo:
    def __init__(self, caminho_json, caminho_vetores):
        self._json = Path(caminho_json)
        self._vetores = Path(caminho_vetores)
        self._cache = None
        self._carregado = False

    def carregar(self):
        if not self._carregado:
            self._cache = self._ler()
            self._carregado = True
            if self._cache is None:
                log.warning("grafo de conceitos não encontrado em %s", self._json.name)
            else:
                log.info("grafo de conceitos carregado: %d nós, %d arestas",
                         len(self._cache.nos), len(self._cache.arestas))
        return self._cache

    def salvar(self, grafo):
        gravar_json(self._json, grafo.como_dict(), indent=1)
        np.savez_compressed(self._vetores, vetores=grafo.vetores.astype("float32"))
        log.info("grafo salvo: %d nós, %d arestas", len(grafo.nos), len(grafo.arestas))
        self._cache, self._carregado = grafo, True

    def invalidar(self):
        self._cache, self._carregado = None, False

    def _ler(self):
        if not self._json.exists() or not self._vetores.exists():
            return None
        return GrafoConceitos.de_dict(ler_json(self._json), np.load(self._vetores)["vetores"])
