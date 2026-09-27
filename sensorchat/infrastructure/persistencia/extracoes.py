from .arquivos import gravar_json, ler_json


class RepositorioExtracoesEmArquivo:
    def __init__(self, caminho):
        self._caminho = caminho

    def carregar(self):
        return ler_json(self._caminho, {})

    def salvar(self, extracoes):
        gravar_json(self._caminho, extracoes)
