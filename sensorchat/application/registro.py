import time
from contextlib import contextmanager


def resumir(texto, limite=80):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


class Cronometro:
    def __init__(self):
        self.segundos = 0.0


@contextmanager
def cronometrar():
    cronometro = Cronometro()
    inicio = time.perf_counter()
    try:
        yield cronometro
    finally:
        cronometro.segundos = time.perf_counter() - inicio
