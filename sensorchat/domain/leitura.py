import re
from dataclasses import dataclass

from .fatiamento import SOBREPOSICAO

EMENDA = "\n\n"
PROCEDENCIA = re.compile(r"\s*\([^()]*\b(z-lib|z-library|1lib|libgen)[^()]*\)", re.IGNORECASE)
HIFEN_DE_QUEBRA = re.compile(r"(?<=[A-Za-zÀ-ÿ])-\n(?=[a-zà-ÿ])")
CHAMADA_DE_CITACAO = re.compile(r"\s*\[\d{1,3}(\s*[,–-]\s*\d{1,3})*\]")


@dataclass(frozen=True)
class BlocoDeLeitura:
    numero: int
    pagina: int | None
    texto: str

    def como_dict(self):
        return {"numero": self.numero, "pagina": self.pagina, "texto": self.texto}


def titulo_de(arquivo):
    nome = re.sub(r"\.pdf$", "", arquivo, flags=re.IGNORECASE)
    return " ".join(PROCEDENCIA.sub("", nome).replace("_", " ").split())


def sem_sobreposicao(texto, anterior=None):
    if anterior is not None:
        cauda = anterior[-SOBREPOSICAO:] + EMENDA
        if texto.startswith(cauda):
            return texto[len(cauda):]
    if texto[SOBREPOSICAO:SOBREPOSICAO + len(EMENDA)] == EMENDA:
        return texto[SOBREPOSICAO + len(EMENDA):]
    return texto


def corrido(texto):
    paragrafos = []
    for paragrafo in texto.split(EMENDA):
        paragrafo = " ".join(HIFEN_DE_QUEBRA.sub("", paragrafo).split())
        if paragrafo:
            paragrafos.append(paragrafo)
    return EMENDA.join(paragrafos)


def montar_blocos(pedacos):
    blocos, anterior = [], None
    for pedaco in pedacos:
        mesma_pagina = anterior is not None and anterior.pagina == pedaco.pagina
        texto = corrido(sem_sobreposicao(pedaco.texto, anterior.texto if mesma_pagina else None))
        anterior = pedaco
        if texto:
            blocos.append(BlocoDeLeitura(len(blocos), pedaco.pagina, texto))
    return blocos


def texto_falado(texto):
    return " ".join(CHAMADA_DE_CITACAO.sub("", texto).split())
