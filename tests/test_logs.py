import logging
import unittest

from sensorchat.infrastructure.logs import FormatoCurto, SemRotasSilenciadas
from sensorchat.infrastructure.modelo_openai import ModeloOpenAI
from sensorchat.domain.conversa import Mensagem

from .test_web import BaseWeb


def _acesso(caminho):
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("127.0.0.1:1", "GET", caminho, "1.1", 200), None)


class TestFiltroDeAcesso(unittest.TestCase):
    def test_silencia_so_o_estado(self):
        filtro = SemRotasSilenciadas()
        self.assertFalse(filtro.filter(_acesso("/estado?desde=3")))
        self.assertTrue(filtro.filter(_acesso("/tutor/perguntar")))
        self.assertTrue(filtro.filter(logging.LogRecord("x", logging.INFO, "", 0, "sem args", None, None)))

    def test_nome_curto(self):
        registro = logging.LogRecord("sensorchat.application.tutor", logging.INFO, "", 0, "oi", None, None)
        self.assertIn("[tutor] oi", FormatoCurto("[%(name)s] %(message)s").format(registro))


class ClienteFalso:
    def __init__(self):
        self.chat = self
        self.completions = self

    def create(self, **_):
        from types import SimpleNamespace as N
        mensagem = N(content="olá", tool_calls=None)
        return N(choices=[N(message=mensagem, finish_reason="stop")],
                 usage=N(prompt_tokens=12, completion_tokens=3))


class TestLogsDoProcesso(BaseWeb):
    def _mensagens(self, acao):
        with self.assertLogs("sensorchat", level="INFO") as capturado:
            acao()
        return "\n".join(capturado.output)

    def test_tutor(self):
        texto = self._mensagens(lambda: self.cliente.post("/tutor/perguntar", json={"pergunta": "o que é deriva?"}))
        for trecho in ["tutor recebeu a pergunta «o que é deriva?»", "rodada 1/4: modelo pediu 1 ferramenta",
                       "executando buscar_na_base: documentos [todos]", "buscando em [todos]",
                       "busca devolveu", "grafo: 1 conceitos ligados", "modelo respondeu após 1 consulta",
                       "tutor respondeu em"]:
            self.assertIn(trecho, texto)

    def test_banca(self):
        texto = self._mensagens(lambda: (self.cliente.post("/falar", json={"autor": "Érica", "texto": "oi"}),
                                         self.cliente.post("/rodada"), self.cliente.post("/fechar-topico"),
                                         self.cliente.post("/publicar")))
        for trecho in ["fala de Érica registrada", "rodada iniciada: Especialista em sensores, Engenheiro embarcado",
                       "vez de Especialista em sensores", "Especialista em sensores falou após 1 consulta",
                       "vez de Engenheiro embarcado", "rodada concluída", "fechando o tópico",
                       "plano atualizado: 1 decisões", "ata publicada em"]:
            self.assertIn(trecho, texto)

    def test_estado_nao_gera_log(self):
        with self.assertNoLogs("sensorchat", level="INFO"):
            self.cliente.get("/estado?desde=0")

    def test_chamada_ao_llm(self):
        modelo = ModeloOpenAI(ClienteFalso())
        with self.assertLogs("sensorchat", level="INFO") as capturado:
            modelo.completar("mimo", [Mensagem.usuario("oi")], 10)
        self.assertIn("enviando ao LLM mimo: 1 mensagens, 2 caracteres", capturado.output[0])
        self.assertIn("resposta do LLM mimo em", capturado.output[1])
        self.assertIn("3 caracteres, tokens 12 → 3", capturado.output[1])


if __name__ == "__main__":
    unittest.main()
