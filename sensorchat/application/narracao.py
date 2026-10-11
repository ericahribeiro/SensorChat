import hashlib
import logging
import re

from ..domain.erros import BlocoInexistente, VozIndisponivel
from ..domain.leitura import texto_falado
from .registro import cronometrar

VOZES = ("mimo_default", "Mia", "Chloe", "Milo", "Dean")
NOME_DE_VOZ = re.compile(r"[\w\- ]{1,40}")

log = logging.getLogger(__name__)


class Narrador:
    def __init__(self, biblioteca, sintetizador, gravacoes):
        self._biblioteca = biblioteca
        self._sintetizador = sintetizador
        self._gravacoes = gravacoes

    def vozes(self):
        return VOZES

    def narrar(self, referencia, numero, voz=None):
        voz = voz or VOZES[0]
        if not NOME_DE_VOZ.fullmatch(voz):
            raise VozIndisponivel(f"voz inválida: '{voz}'")
        documento, blocos = self._biblioteca.abrir(referencia)
        if not 0 <= numero < len(blocos):
            raise BlocoInexistente(numero)

        texto = texto_falado(blocos[numero].texto)
        chave = hashlib.sha1(f"{self._sintetizador.modelo}|{voz}|{texto}".encode("utf-8")).hexdigest()
        audio = self._gravacoes.ler(chave)
        if audio is not None:
            return audio

        log.info("narrando %s trecho %d com a voz %s: %d caracteres", documento.item.id, numero, voz, len(texto))
        with cronometrar() as tempo:
            audio = self._sintetizador.sintetizar(texto, voz)
        log.info("narração pronta em %.1fs: %d kB", tempo.segundos, len(audio) // 1024)
        self._gravacoes.gravar(chave, audio)
        return audio
