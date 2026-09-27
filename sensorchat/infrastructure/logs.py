import logging
import os

RAIZ = "sensorchat"
ROTAS_SILENCIADAS = ("/estado",)
FORMATO = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
FORMATO_HORA = "%H:%M:%S"


class FormatoCurto(logging.Formatter):
    def format(self, record):
        record.name = record.name.removeprefix(RAIZ + ".").rsplit(".", 1)[-1]
        return super().format(record)


class SemRotasSilenciadas(logging.Filter):
    def filter(self, record):
        argumentos = record.args if isinstance(record.args, tuple) else ()
        caminho = str(argumentos[2]) if len(argumentos) >= 3 else ""
        return not caminho.startswith(ROTAS_SILENCIADAS)


def configurar(nivel=None):
    nivel = (nivel or os.environ.get("SENSORCHAT_LOG", "INFO")).upper()
    logger = logging.getLogger(RAIZ)
    if not any(isinstance(h.formatter, FormatoCurto) for h in logger.handlers):
        saida = logging.StreamHandler()
        saida.setFormatter(FormatoCurto(FORMATO, FORMATO_HORA))
        logger.addHandler(saida)
    logger.setLevel(nivel)
    logger.propagate = False

    acesso = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, SemRotasSilenciadas) for f in acesso.filters):
        acesso.addFilter(SemRotasSilenciadas())
