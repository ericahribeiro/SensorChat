from datetime import datetime, timezone
from pathlib import Path

from .arquivos import gravar_json


class AvisoDeIndexacao:
    """Grava um arquivo ao fim de cada indexação com documentos novos; o
    scripts/sincronizar_dados.sh o procura para enviar as bases ao GitHub."""

    def __init__(self, caminho):
        self._caminho = Path(caminho)

    def __call__(self, novos):
        gravar_json(self._caminho, {"novos": list(novos),
                                    "quando": datetime.now(timezone.utc).isoformat(timespec="seconds")})
