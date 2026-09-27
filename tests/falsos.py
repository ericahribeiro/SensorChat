import json
import re
import zlib

import numpy as np

from sensorchat.domain.conversa import ChamadaFerramenta, RespostaModelo

DIMENSAO = 64


class VetorizadorFalso:
    def _vetor(self, texto):
        vetor = np.zeros(DIMENSAO, "float32")
        for palavra in re.findall(r"\w+", texto.lower()):
            vetor[zlib.crc32(palavra.encode()) % DIMENSAO] += 1
        norma = np.linalg.norm(vetor)
        return vetor / norma if norma else vetor

    def vetorizar_documentos(self, textos, lote=32):
        return np.array([self._vetor(t) for t in textos], dtype="float32").reshape(len(textos), DIMENSAO)

    def vetorizar_pergunta(self, texto):
        return self._vetor(texto)


class ModeloFalso:
    def __init__(self, roteiro):
        self._roteiro = roteiro
        self.chamadas = []

    def completar(self, modelo, mensagens, max_tokens, ferramentas=(), sem_raciocinio=False):
        self.chamadas.append({"modelo": modelo, "mensagens": list(mensagens),
                              "ferramentas": bool(ferramentas), "sem_raciocinio": sem_raciocinio})
        return self._roteiro(modelo, list(mensagens), ferramentas)


def fala(texto):
    return RespostaModelo(texto)


def chamada(nome, argumentos, id_="call_1"):
    return RespostaModelo("", (ChamadaFerramenta(id_, nome, json.dumps(argumentos)),))
