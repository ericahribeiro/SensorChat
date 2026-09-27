import logging
from pathlib import Path

import numpy as np

from ...domain.documentos import BaseVetorial, Pedaco
from ...domain.erros import BaseInexistente
from .arquivos import gravar_json, ler_json

BASES = ("artigos", "livros")

log = logging.getLogger(__name__)


class RepositorioBasesEmArquivo:
    def __init__(self, raiz, nomes=BASES):
        self._raiz = Path(raiz)
        self._nomes = tuple(nomes)

    def nomes(self):
        return self._nomes

    def carregar(self, nome):
        vetores, pedacos = self._caminhos(nome)
        if not vetores.exists() or not pedacos.exists():
            raise BaseInexistente(nome)
        return BaseVetorial(nome, np.load(vetores)["vetores"],
                            [Pedaco.de_dict(p) for p in ler_json(pedacos)])

    def salvar(self, nome, vetores, pedacos):
        caminho_vetores, caminho_pedacos = self._caminhos(nome)
        np.savez_compressed(caminho_vetores, vetores=vetores)
        gravar_json(caminho_pedacos, [p.como_dict() for p in pedacos])
        log.info("base '%s' salva: %d pedaços em %s", nome, len(pedacos), caminho_vetores.name)

    def _caminhos(self, nome):
        return self._raiz / f"base_{nome}.npz", self._raiz / f"base_{nome}.json"
