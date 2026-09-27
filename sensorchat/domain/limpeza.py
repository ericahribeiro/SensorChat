import re
from collections import Counter
from dataclasses import dataclass

MARGEM = 0.08
LIMIAR_BORDA = 0.30
LIMIAR_QUALQUER = 0.50
MAX_CHARS_CABECALHO = 200
MAX_CHARS_REPETIDO = 150

PADRAO_REFERENCIAS = re.compile(
    r"^\s*(references|bibliography|referências|referencias|works cited)\s*$",
    re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class Bloco:
    texto: str
    topo: float
    base: float
    altura_pagina: float

    @property
    def na_borda(self):
        altura = self.altura_pagina or 1
        return self.base <= altura * MARGEM or self.topo >= altura * (1 - MARGEM)

    @property
    def assinatura(self):
        return re.sub(r"\d+", "#", " ".join(self.texto.split())).lower()


@dataclass(frozen=True)
class PaginaBruta:
    numero: int
    blocos: tuple


@dataclass(frozen=True)
class Pagina:
    numero: int
    texto: str


def _repetidas(frequencia, total_paginas, limiar):
    minimo = max(2, int(total_paginas * limiar))
    return {a for a, c in frequencia.items() if c >= minimo and len(a) > 2}


def limpar_paginas(paginas):
    freq_borda, freq_qualquer = Counter(), Counter()
    for pagina in paginas:
        freq_borda.update({b.assinatura for b in pagina.blocos
                           if b.na_borda and len(b.texto) <= MAX_CHARS_CABECALHO})
        freq_qualquer.update({b.assinatura for b in pagina.blocos
                              if len(b.texto) <= MAX_CHARS_REPETIDO})

    lixo_borda = _repetidas(freq_borda, len(paginas), LIMIAR_BORDA)
    lixo_qualquer = _repetidas(freq_qualquer, len(paginas), LIMIAR_QUALQUER)

    def descartar(bloco):
        return ((bloco.na_borda and bloco.assinatura in lixo_borda)
                or (len(bloco.texto) <= MAX_CHARS_REPETIDO and bloco.assinatura in lixo_qualquer))

    limpas = []
    for pagina in paginas:
        mantidos = "\n\n".join(b.texto.strip() for b in pagina.blocos if not descartar(b))
        limpas.append(Pagina(pagina.numero, re.sub(r"\n{3,}", "\n\n", mantidos)))
    return limpas, lixo_borda | lixo_qualquer


def cortar_referencias(paginas, nao_antes_de=0.40):
    total = max(len(paginas), 1)
    for i in range(len(paginas) - 1, -1, -1):
        if i / total < nao_antes_de:
            break
        ocorrencias = list(PADRAO_REFERENCIAS.finditer(paginas[i].texto))
        if ocorrencias:
            pagina = paginas[i]
            cortada = Pagina(pagina.numero, pagina.texto[:ocorrencias[-1].start()])
            return paginas[:i] + [cortada], pagina.numero
    return paginas, None
