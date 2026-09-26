import re
from collections import Counter

import pymupdf

MARGEM = 0.08
LIMIAR_BORDA = 0.30
LIMIAR_QUALQUER = 0.50
MAX_CHARS_CABECALHO = 200
MAX_CHARS_REPETIDO = 150


def _assinatura(txt):
    return re.sub(r"\d+", "#", " ".join(txt.split())).lower()


def ler_paginas(caminho):

    doc = pymupdf.open(caminho)
    paginas_blocos = []

    for i, pagina in enumerate(doc):
        altura = pagina.rect.height or 1
        blocos = []
        for b in pagina.get_text("blocks", sort=True):
            x0, y0, x1, y1, texto = b[0], b[1], b[2], b[3], b[4]
            na_borda = (y1 <= altura * MARGEM) or (y0 >= altura * (1 - MARGEM))
            blocos.append({"y": y0, "texto": texto, "borda": na_borda})
        paginas_blocos.append((i + 1, blocos))

    n = len(paginas_blocos)

    freq_borda = Counter()
    freq_qualquer = Counter()
    for _, blocos in paginas_blocos:
        freq_borda.update({_assinatura(b["texto"]) for b in blocos
                           if b["borda"] and len(b["texto"]) <= MAX_CHARS_CABECALHO})
        freq_qualquer.update({_assinatura(b["texto"]) for b in blocos
                              if len(b["texto"]) <= MAX_CHARS_REPETIDO})

    lixo_borda = {a for a, c in freq_borda.items()
                  if c >= max(2, int(n * LIMIAR_BORDA)) and len(a) > 2}
    lixo_qualquer = {a for a, c in freq_qualquer.items()
                     if c >= max(2, int(n * LIMIAR_QUALQUER)) and len(a) > 2}
    lixo = lixo_borda | lixo_qualquer

    paginas = []
    for num, blocos in paginas_blocos:
        mantidos = [b["texto"] for b in blocos
                    if not ((b["borda"] and _assinatura(b["texto"]) in lixo_borda)
                            or (len(b["texto"]) <= MAX_CHARS_REPETIDO
                                and _assinatura(b["texto"]) in lixo_qualquer))]
        texto = re.sub(r"\n{3,}", "\n\n", "\n\n".join(t.strip() for t in mantidos))
        paginas.append((num, texto))

    return paginas, lixo


PADRAO_REF = re.compile(
    r"^\s*(references|bibliography|referências|referencias|works cited)\s*$",
    re.IGNORECASE | re.MULTILINE)


def cortar_referencias(paginas, nao_antes_de=0.40):
    n = max(len(paginas), 1)
    for i in range(len(paginas) - 1, -1, -1):
        if i / n < nao_antes_de:
            break
        num, texto = paginas[i]
        m = None
        for m in PADRAO_REF.finditer(texto):
            pass
        if m:
            return paginas[:i] + [(num, texto[:m.start()])], num
    return paginas, None