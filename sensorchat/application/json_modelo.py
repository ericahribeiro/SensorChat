import json

from ..domain.erros import RespostaInvalida


def ler_json(texto):
    bruto = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise RespostaInvalida(bruto) from erro
