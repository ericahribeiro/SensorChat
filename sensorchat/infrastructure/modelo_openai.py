import logging

from ..application.registro import cronometrar
from ..domain.conversa import ChamadaFerramenta, RespostaModelo

SEM_RACIOCINIO = {"thinking": {"type": "disabled"}}

log = logging.getLogger(__name__)


def _tokens(resposta):
    uso = getattr(resposta, "usage", None)
    entrada = getattr(uso, "prompt_tokens", None)
    saida = getattr(uso, "completion_tokens", None)
    return f", tokens {entrada} → {saida}" if entrada is not None and saida is not None else ""


class ModeloOpenAI:
    def __init__(self, cliente):
        self._cliente = cliente

    @classmethod
    def conectar(cls, configuracao):
        from openai import OpenAI
        return cls(OpenAI(api_key=configuracao.api_key, base_url=configuracao.base_url))

    def completar(self, modelo, mensagens, max_tokens, ferramentas=(), sem_raciocinio=False):
        argumentos = {
            "model": modelo,
            "messages": [self._mensagem(m) for m in mensagens],
            "max_completion_tokens": max_tokens,
            "extra_body": SEM_RACIOCINIO if sem_raciocinio else {},
        }
        if ferramentas:
            argumentos["tools"] = [self._ferramenta(f) for f in ferramentas]

        log.info("enviando ao LLM %s: %d mensagens, %d caracteres%s", modelo, len(mensagens),
                 sum(len(m.conteudo) for m in mensagens),
                 f", ferramentas: {', '.join(f.nome for f in ferramentas)}" if ferramentas else "")
        try:
            with cronometrar() as tempo:
                bruta = self._cliente.chat.completions.create(**argumentos)
        except Exception as erro:
            log.error("falha na chamada ao LLM %s após %.1fs: %s", modelo, tempo.segundos, erro)
            raise

        escolha = bruta.choices[0]
        chamadas = tuple(
            ChamadaFerramenta(c.id, c.function.name, c.function.arguments or "")
            for c in escolha.message.tool_calls or [])
        resposta = RespostaModelo(escolha.message.content or "", chamadas, escolha.finish_reason == "length")

        conteudo = (f"pediu ferramentas: {', '.join(c.nome for c in chamadas)}" if chamadas
                    else f"{len(resposta.texto)} caracteres")
        log.info("resposta do LLM %s em %.1fs: %s%s", modelo, tempo.segundos, conteudo, _tokens(bruta))
        if resposta.interrompida:
            log.warning("resposta do LLM %s cortada pelo limite de %d tokens", modelo, max_tokens)
        return resposta

    @staticmethod
    def _mensagem(mensagem):
        dados = {"role": mensagem.papel, "content": mensagem.conteudo}
        if mensagem.chamadas:
            dados["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.nome, "arguments": c.argumentos}}
                for c in mensagem.chamadas]
        if mensagem.id_chamada:
            dados["tool_call_id"] = mensagem.id_chamada
        return dados

    @staticmethod
    def _ferramenta(ferramenta):
        return {"type": "function", "function": {
            "name": ferramenta.nome,
            "description": ferramenta.descricao,
            "parameters": ferramenta.parametros,
        }}
