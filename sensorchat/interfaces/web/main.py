from ...container import Container
from ...infrastructure import logs
from ...infrastructure.configuracao import ChaveAusente, Configuracao
from .aplicacao import criar_app

logs.configurar()

try:
    app = criar_app(Container(Configuracao.do_ambiente().exigir_chave()))
except ChaveAusente as erro:
    raise SystemExit(str(erro))
