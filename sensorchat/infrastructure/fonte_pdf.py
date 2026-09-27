from pathlib import Path

from ..domain.limpeza import Bloco, PaginaBruta


class FontePdfLocal:
    def __init__(self, raiz):
        self._raiz = Path(raiz)

    def local(self, base):
        return f"pdfs_{base}"

    def listar(self, base):
        pasta = self._raiz / self.local(base)
        pasta.mkdir(parents=True, exist_ok=True)
        return [str(p) for p in sorted(pasta.glob("*.pdf"))]

    def ler(self, caminho):
        import pymupdf
        with pymupdf.open(caminho) as documento:
            return [
                PaginaBruta(numero, tuple(
                    Bloco(texto=b[4], topo=b[1], base=b[3], altura_pagina=pagina.rect.height)
                    for b in pagina.get_text("blocks", sort=True)))
                for numero, pagina in enumerate(documento, start=1)
            ]
