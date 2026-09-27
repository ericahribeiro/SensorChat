import logging

from ...domain.documentos import Descricao
from .arquivos import gravar_json, ler_json

log = logging.getLogger(__name__)


class RepositorioCatalogoEmArquivo:
    def __init__(self, caminho):
        self._caminho = caminho

    def descricoes(self):
        return {d["arquivo"]: Descricao.de_dict(d) for d in ler_json(self._caminho, [])}

    def salvar(self, descricoes):
        gravar_json(self._caminho, [d.como_dict() for d in descricoes], indent=1)
        log.info("catálogo salvo: %d documentos descritos", len(descricoes))
