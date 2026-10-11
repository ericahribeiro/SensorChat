import logging
import threading

from ..domain.erros import AtualizacaoEmAndamento
from .extracao import RESUMOS

log = logging.getLogger(__name__)


class Diario:
    def __init__(self, eco=None):
        self._eco = eco
        self._linhas = []
        self._trava = threading.Lock()

    def __call__(self, texto):
        if self._eco:
            self._eco(texto)
        with self._trava:
            self._linhas.extend(linha for linha in str(texto).split("\n") if linha.strip())

    def limpar(self):
        with self._trava:
            self._linhas.clear()

    def linhas(self):
        with self._trava:
            return list(self._linhas)


class AtualizarBiblioteca:

    def __init__(self, indexar, descrever, extrair, busca, avisar=print):
        self._indexar = indexar
        self._descrever = descrever
        self._extrair = extrair
        self._busca = busca
        self._avisar = avisar

    def executar(self):
        novos = []
        for base in self._busca.nomes():
            self._avisar(f"Procurando PDFs novos em '{base}'...")
            novos += self._indexar.acrescentar(base)
        self._busca.recarregar()
        if not novos:
            self._avisar("Nenhum documento novo: a base e o grafo continuam como estavam.")
            return novos

        self._avisar("\nDescrevendo os documentos novos para o catálogo...")
        self._descrever.executar()
        self._avisar("\nExtraindo conceitos e relações para o grafo...")
        self._extrair.executar(RESUMOS)
        self._avisar(f"\nBiblioteca atualizada: {len(novos)} documento(s) novo(s).")
        return novos


class AtualizacaoEmSegundoPlano:
    def __init__(self, atualizar, diario):
        self._atualizar = atualizar
        self._diario = diario
        self._trava = threading.Lock()
        self._tarefa = None
        self._novos = []
        self._erro = ""

    def iniciar(self):
        with self._trava:
            if self.ocupada:
                raise AtualizacaoEmAndamento()
            self._diario.limpar()
            self._novos, self._erro = [], ""
            self._tarefa = threading.Thread(target=self._rodar, name="atualizar-biblioteca", daemon=True)
            self._tarefa.start()

    @property
    def ocupada(self):
        return self._tarefa is not None and self._tarefa.is_alive()

    def aguardar(self, segundos=None):
        if self._tarefa is not None:
            self._tarefa.join(segundos)

    def estado(self):
        return {"ocupada": self.ocupada, "linhas": self._diario.linhas(),
                "novos": list(self._novos), "erro": self._erro}

    def _rodar(self):
        try:
            self._novos = self._atualizar.executar()
        except Exception as erro:
            log.exception("a atualização da biblioteca falhou")
            self._erro = str(erro) or type(erro).__name__
