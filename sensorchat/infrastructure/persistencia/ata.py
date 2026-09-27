import threading

from ...domain.ata import Ata
from .arquivos import gravar_json, ler_json


class RepositorioAtaEmArquivo:
    def __init__(self, caminho):
        self._caminho = caminho
        self._trava = threading.Lock()

    def ler(self):
        dados = ler_json(self._caminho)
        return Ata.de_dict(dados) if dados else Ata()

    def alterar(self, alteracao):
        with self._trava:
            ata = self.ler()
            resultado = alteracao(ata)
            gravar_json(self._caminho, ata.como_dict(), indent=1)
            return resultado
