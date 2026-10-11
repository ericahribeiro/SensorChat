from .documentos import Pedaco

ALVO_PEDACO = 900
SOBREPOSICAO = 150
MIN_PARAGRAFO = 40
MIN_PEDACO = 250


def picar(paginas, arquivo):
    pedacos = []
    for pagina in paginas:
        paragrafos = [p.strip() for p in pagina.texto.split("\n\n") if len(p.strip()) > MIN_PARAGRAFO]
        buffer = ""
        for paragrafo in paragrafos:
            if len(buffer) + len(paragrafo) < ALVO_PEDACO:
                buffer += ("\n\n" if buffer else "") + paragrafo
                continue
            if buffer:
                pedacos.append(Pedaco(arquivo, pagina.numero, buffer))
            buffer = (buffer[-SOBREPOSICAO:] + "\n\n" + paragrafo) if buffer else paragrafo
        if buffer:
            pedacos.append(Pedaco(arquivo, pagina.numero, buffer))
    return [p for p in pedacos if len(p.texto) >= MIN_PEDACO]
