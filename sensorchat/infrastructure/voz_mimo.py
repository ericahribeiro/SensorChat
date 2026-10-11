import base64
import logging

from ..domain.erros import VozIndisponivel

FORMATO = "mp3"

log = logging.getLogger(__name__)


class VozMimo:
    def __init__(self, cliente, modelo):
        self._cliente = cliente
        self.modelo = modelo

    @classmethod
    def conectar(cls, configuracao):
        from openai import OpenAI
        return cls(OpenAI(api_key=configuracao.api_key, base_url=configuracao.base_url),
                   configuracao.modelo_voz)

    def sintetizar(self, texto, voz):
        try:
            bruta = self._cliente.chat.completions.create(
                model=self.modelo,
                messages=[{"role": "assistant", "content": texto}],
                extra_body={"audio": {"format": FORMATO, "voice": voz}})
        except Exception as erro:
            log.error("a Xiaomi recusou a narração com %s (voz %s): %s", self.modelo, voz, erro)
            raise VozIndisponivel(f"a Xiaomi recusou a narração: {erro}") from erro

        audio = getattr(bruta.choices[0].message, "audio", None)
        dados = audio.get("data") if isinstance(audio, dict) else getattr(audio, "data", None)
        if not dados:
            log.error("o modelo %s respondeu sem áudio: %s", self.modelo, str(bruta)[:600])
            raise VozIndisponivel(f"o modelo {self.modelo} respondeu sem áudio")
        return base64.b64decode(dados)
