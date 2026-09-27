import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from ..domain.ata import AGENTE, HUMANO, Plano
from ..domain.banca import AGENTES, ORDEM_DA_RODADA, RESUMIDOR
from ..domain.conversa import Mensagem
from ..domain.erros import BancaOcupada, FalaVazia, RespostaInvalida
from .json_modelo import ler_json
from .registro import cronometrar, resumir

MODELO_RESUMIDOR = "mimo-v2.5"
MAX_TOKENS_FALA = 700
MAX_TOKENS_RESUMO = 900
LIMITE_ATA_RESUMO = 200
CONTEXTO_BUSCA_CEGA = 500

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EstadoDaBanca:
    linhas: list
    total: int
    plano: Plano
    ocupada: bool


class Banca:
    def __init__(self, atas, modelo_linguagem, roteador, publicador,
                 agentes=AGENTES, ordem=ORDEM_DA_RODADA, relogio=datetime.now):
        self._atas = atas
        self._modelo = modelo_linguagem
        self._roteador = roteador
        self._publicador = publicador
        self._agentes = agentes
        self._ordem = ordem
        self._relogio = relogio
        self._falando = threading.Lock()

    def estado(self, desde=0):
        ata = self._atas.ler()
        return EstadoDaBanca(ata.linhas[desde:], len(ata.linhas), ata.plano, self._falando.locked())

    def registrar_fala(self, autor, texto):
        if not texto.strip():
            log.warning("fala vazia recusada")
            raise FalaVazia()
        autor = autor.strip() or "Anônimo"
        self._acrescentar(autor, HUMANO, texto)
        log.info("fala de %s registrada na ata: «%s»", autor, resumir(texto))

    def rodada(self, quem=None):
        with self._exclusivo():
            alvos = [quem] if quem in self._agentes else list(self._ordem)
            log.info("rodada iniciada: %s", ", ".join(self._agentes[c].nome for c in alvos))
            with cronometrar() as tempo:
                for chave in alvos:
                    self._turno(self._agentes[chave])
            log.info("rodada concluída em %.1fs", tempo.segundos)
            return alvos

    def fechar_topico(self):
        with self._exclusivo():
            ata = self._atas.ler()
            log.info("fechando o tópico: resumindo %d falas", len(ata.linhas[-LIMITE_ATA_RESUMO:]))
            resposta = self._modelo.completar(
                MODELO_RESUMIDOR,
                [Mensagem.sistema(RESUMIDOR), Mensagem.usuario(ata.em_texto(LIMITE_ATA_RESUMO))],
                MAX_TOKENS_RESUMO, sem_raciocinio=True)
            try:
                plano = Plano.de_dict(ler_json(resposta.texto_completo()))
            except RespostaInvalida:
                log.warning("o resumidor não devolveu JSON válido; o plano não foi alterado")
                raise
            self._atas.alterar(lambda atual: atual.definir_plano(plano))
            log.info("plano atualizado: %d decisões, %d em aberto, %d riscos",
                     len(plano.decisoes), len(plano.abertas), len(plano.riscos))
            return plano

    def publicar(self):
        destino = self._publicador.publicar(self._atas.ler(), self._relogio())
        log.info("ata publicada em %s", destino)
        return destino

    @contextmanager
    def _exclusivo(self):
        if not self._falando.acquire(blocking=False):
            log.warning("pedido recusado: a banca já está falando")
            raise BancaOcupada()
        try:
            yield
        finally:
            self._falando.release()

    def _turno(self, agente):
        ata = self._atas.ler()
        texto_da_ata = ata.em_texto()
        convite = Mensagem.usuario(agente.convite(texto_da_ata))
        log.info("vez de %s (%s, %s)", agente.nome, agente.modelo,
                 "consulta a base" if agente.usa_rag else "sem consulta à base")

        if not agente.usa_rag:
            resposta = self._modelo.completar(
                agente.modelo, [Mensagem.sistema(agente.sistema), convite],
                MAX_TOKENS_FALA, sem_raciocinio=True)
            self._acrescentar(agente.nome, AGENTE, resposta.texto_completo())
            log.info("%s falou: «%s»", agente.nome, resumir(resposta.texto))
            return

        resposta, consultas = self._roteador.responder(
            agente.modelo,
            [Mensagem.sistema(agente.sistema + self._roteador.bloco_catalogo()), convite],
            MAX_TOKENS_FALA,
            sem_raciocinio=True,
            busca_cega=ata.ultima_fala_humana() or texto_da_ata[-CONTEXTO_BUSCA_CEGA:],
            cotas=agente.cotas)
        self._acrescentar(agente.nome, AGENTE, resposta.texto_completo(), consultas)
        log.info("%s falou após %d consulta(s): «%s»", agente.nome, len(consultas), resumir(resposta.texto))

    def _acrescentar(self, autor, papel, texto, consultas=()):
        quando = self._relogio().isoformat(timespec="seconds")
        self._atas.alterar(lambda ata: ata.acrescentar(autor, papel, texto, quando, consultas))
