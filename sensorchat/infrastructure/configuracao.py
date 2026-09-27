import os
from dataclasses import dataclass
from pathlib import Path

URL_PADRAO = "https://api.xiaomimimo.com/v1"


class ChaveAusente(Exception):
    def __init__(self):
        super().__init__("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")


def _carregar_dotenv():
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    load_dotenv(find_dotenv(usecwd=True))


@dataclass(frozen=True)
class Configuracao:
    raiz: Path
    api_key: str = ""
    base_url: str = URL_PADRAO
    banca_usuario: str = "banca"
    banca_senha: str = ""

    @classmethod
    def do_ambiente(cls):
        _carregar_dotenv()
        return cls(
            raiz=Path(os.environ.get("SENSORCHAT_RAIZ", ".")).resolve(),
            api_key=os.environ.get("MIMO_API_KEY", ""),
            base_url=os.environ.get("MIMO_BASE_URL", URL_PADRAO),
            banca_usuario=os.environ.get("BANCA_USUARIO", "banca"),
            banca_senha=os.environ.get("BANCA_SENHA", ""),
        )

    def exigir_chave(self):
        if not self.api_key:
            raise ChaveAusente()
        return self
