import numpy as np

from ..domain.conversa import Mensagem
from ..domain.documentos import Descricao
from . import instrucoes
from .json_modelo import ler_json

MODELO = "mimo-v2.5"
AMOSTRA = 40
MAX_CHARS_PEDACO = 900
MAX_TOKENS = 2000


def amostrar(pedacos):
    indices = np.linspace(0, len(pedacos) - 1, min(len(pedacos), AMOSTRA)).astype(int)
    return [pedacos[i] for i in sorted(set(indices))]


class DescreverDocumentos:
    def __init__(self, busca, catalogo, modelo_linguagem, avisar=print):
        self._busca = busca
        self._catalogo = catalogo
        self._modelo = modelo_linguagem
        self._avisar = avisar

    def executar(self, tudo=False, filtro=None):
        filtro = filtro.lower() if filtro else None
        existentes = self._catalogo.descricoes()
        feitos, falhas = 0, []

        for nome in self._busca.nomes():
            base = self._busca.base(nome)
            if base is None:
                self._avisar(f"  (aviso: base '{nome}' não existe)")
                continue
            for arquivo, pedacos in base.por_arquivo().items():
                if filtro and filtro not in arquivo.lower():
                    continue
                if not tudo and not filtro and arquivo in existentes and existentes[arquivo].descricao:
                    continue
                try:
                    existentes[arquivo] = self._descrever(nome, arquivo, pedacos)
                except Exception as erro:
                    falhas.append((arquivo, str(erro)[:120]))
                    self._avisar(f"  {arquivo[:64]} ({len(pedacos)} trechos)... FALHOU: {erro}")
                    continue
                feitos += 1
                self._avisar(f"  {arquivo[:64]} ({len(pedacos)} trechos)... ok")
                self._catalogo.salvar(list(existentes.values()))

        self._avisar(f"\n{feitos} descritos, {len(existentes)} no catálogo")
        for arquivo, erro in falhas:
            self._avisar(f"  falhou {arquivo[:50]}: {erro}")
        return feitos

    def _descrever(self, base, arquivo, pedacos):
        amostra = amostrar(pedacos)
        corpo = "\n\n---\n\n".join(
            f"(página {p.pagina})\n{p.texto[:MAX_CHARS_PEDACO]}" for p in amostra)
        resposta = self._modelo.completar(
            MODELO,
            [Mensagem.sistema(instrucoes.DESCREVER),
             Mensagem.usuario(instrucoes.pedido_de_descricao(
                 arquivo, len(pedacos), min(len(pedacos), AMOSTRA), corpo))],
            MAX_TOKENS, sem_raciocinio=True)
        dados = ler_json(resposta.texto)
        return Descricao(arquivo, base, dados["descricao"].strip(), dados["resumo"].strip())
