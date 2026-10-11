import logging
from dataclasses import dataclass

from ..domain.conversa import Mensagem
from ..domain.erros import PerguntaVazia
from . import instrucoes
from .registro import cronometrar, resumir

MODELO = "mimo-v2.5-pro"
COTAS = {"artigos": 4, "livros": 2}
HISTORICO = 8
MAX_TOKENS = 1500

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RespostaDoTutor:
    resposta: str
    consultas: list
    conceitos: list


class Tutor:
    def __init__(self, roteador, modelo=MODELO, cotas=COTAS, historico=HISTORICO):
        self._roteador = roteador
        self._modelo = modelo
        self._cotas = cotas
        self._historico = historico

    def perguntar(self, pergunta, historico=(), cotas=None):
        pergunta = pergunta.strip()
        if not pergunta:
            log.warning("tutor recebeu pergunta vazia")
            raise PerguntaVazia()
        historico = list(historico)[-self._historico:]
        log.info("tutor recebeu a pergunta «%s» (histórico: %d mensagens)", resumir(pergunta), len(historico))
        mensagens = [Mensagem.sistema(instrucoes.TUTOR + self._roteador.bloco_catalogo()),
                     *historico,
                     Mensagem.usuario(pergunta)]
        with cronometrar() as tempo:
            resposta, consultas = self._roteador.responder(
                self._modelo, mensagens, MAX_TOKENS, busca_cega=pergunta, cotas=cotas or self._cotas)
        conceitos = list(dict.fromkeys(c for consulta in consultas for c in consulta.conceitos or ()))
        log.info("tutor respondeu em %.1fs: %d consulta(s), %d conceito(s) do grafo",
                 tempo.segundos, len(consultas), len(conceitos))
        return RespostaDoTutor(resposta.texto.strip() or "[resposta vazia]", consultas, conceitos)
