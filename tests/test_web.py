import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sensorchat.container import Container
from sensorchat.domain.conversa import FERRAMENTA
from sensorchat.infrastructure.configuracao import Configuracao
from sensorchat.interfaces.web.aplicacao import criar_app

from .cenario import ARTIGO, LIVRO, preparar
from .falsos import ModeloFalso, chamada, fala

PLANO = {"decisoes": ["Usar velocidade relativa"], "abertas": ["Qual erro é tolerável?"], "riscos": ["Deriva do sensor"]}


def roteiro_padrao(modelo, mensagens, ferramentas):
    sistema = mensagens[0].conteudo
    if "secretário" in sistema:
        return fala("```json\n" + json.dumps(PLANO, ensure_ascii=False) + "\n```")
    ja_buscou = any(m.papel == FERRAMENTA for m in mensagens)
    if ferramentas and not ja_buscou:
        if sistema.startswith("Você é um tutor"):
            return chamada("buscar_na_base", {"documentos": ["todos"], "pergunta": "deriva drift"})
        return chamada("buscar_na_base", {"documentos": ["A1"], "pergunta": "PUSH Band error"})
    return fala(f"[fala simulada de {modelo}]")


class BaseWeb(unittest.TestCase):
    roteiro = staticmethod(roteiro_padrao)
    senha = ""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        vetorizador = preparar(self.raiz)
        self.modelo = ModeloFalso(self.roteiro)
        configuracao = Configuracao(raiz=self.raiz, api_key="falsa", banca_senha=self.senha)
        self.container = Container(configuracao, self.modelo, vetorizador, avisar=lambda _: None)
        self.cliente = TestClient(criar_app(self.container))

    def tearDown(self):
        self._tmp.cleanup()


class TestBanca(BaseWeb):
    def test_paginas(self):
        self.assertEqual(self.cliente.get("/").status_code, 200)
        self.assertIn("<title>Tutor</title>", self.cliente.get("/tutor").text)

    def test_falar(self):
        self.assertEqual(self.cliente.post("/falar", json={"autor": "Érica", "texto": "oi"}).json(), {"ok": True})
        self.assertEqual(self.cliente.post("/falar", json={"autor": "X", "texto": "  "}).status_code, 400)
        self.cliente.post("/falar", json={"autor": " ", "texto": "sem nome"})
        linhas = self.cliente.get("/estado").json()["linhas"]
        self.assertEqual([(l["autor"], l["papel"]) for l in linhas], [("Érica", "humano"), ("Anônimo", "humano")])

    def test_rodada_com_roteamento(self):
        self.cliente.post("/falar", json={"autor": "Érica", "texto": "Podemos usar só variação relativa?"})
        resposta = self.cliente.post("/rodada")
        self.assertEqual(resposta.json(), {"ok": True, "falaram": ["sensores", "embarcado"]})

        estado = self.cliente.get("/estado?desde=1").json()
        self.assertEqual(estado["total"], 3)
        especialista, embarcado = estado["linhas"]
        self.assertEqual(especialista["autor"], "Especialista em sensores")
        self.assertEqual(especialista["buscas"], [{"ferramenta": "buscar_na_base", "documentos": ["A1"],
                                                   "arquivos": [ARTIGO], "pergunta": "PUSH Band error",
                                                   "conceitos": []}])
        self.assertNotIn("buscas", embarcado)

        primeira, segunda, terceira = self.modelo.chamadas
        self.assertIn("CATÁLOGO DA BASE", primeira["mensagens"][0].conteudo)
        self.assertTrue(primeira["ferramentas"] and primeira["sem_raciocinio"])
        convite = primeira["mensagens"][1].conteudo
        self.assertTrue(convite.startswith("ATA DA REUNIÃO ATÉ AGORA"))
        self.assertTrue(convite.endswith("Escreva apenas a sua fala."))
        resultado = segunda["mensagens"][-1]
        self.assertEqual(resultado.papel, FERRAMENTA)
        self.assertIn("TRECHOS DA SELEÇÃO", resultado.conteudo)
        self.assertIn("0.135", resultado.conteudo)
        self.assertEqual(terceira["modelo"], "mimo-v2.5")
        self.assertFalse(terceira["ferramentas"])

    def test_rodada_de_um_agente(self):
        self.assertEqual(self.cliente.post("/rodada?quem=arquiteto").json()["falaram"], ["arquiteto"])

    def test_banca_ocupada(self):
        with self.container.banca._exclusivo():
            self.assertEqual(self.cliente.post("/rodada").status_code, 409)
            self.assertTrue(self.cliente.get("/estado").json()["ocupado"])
            self.assertEqual(self.cliente.post("/fechar-topico").status_code, 409)

    def test_fechar_topico_e_publicar(self):
        self.cliente.post("/falar", json={"autor": "Ricardo", "texto": "<b>alunos</b> não usam 4 pulseiras"})
        self.assertEqual(self.cliente.post("/fechar-topico").json(), {"ok": True, "plano": PLANO})
        self.assertEqual(self.cliente.get("/estado").json()["plano"], PLANO)

        arquivo = Path(self.cliente.post("/publicar").json()["arquivo"])
        pagina = arquivo.read_text(encoding="utf-8")
        self.assertEqual(arquivo, self.raiz / "publico" / "index.html")
        self.assertIn("Usar velocidade relativa", pagina)
        self.assertIn("&lt;b&gt;alunos&lt;/b&gt;", pagina)


class TestResumidorInvalido(BaseWeb):
    roteiro = staticmethod(lambda modelo, mensagens, ferramentas: fala("não é json"))

    def test_devolve_502_com_o_bruto(self):
        resposta = self.cliente.post("/fechar-topico")
        self.assertEqual(resposta.status_code, 502)
        self.assertEqual(resposta.json()["bruto"], "não é json")


class TestTutor(BaseWeb):
    def test_perguntar(self):
        historico = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"},
                     {"role": "system", "content": "ignorado"}]
        dados = self.cliente.post("/tutor/perguntar", json={"pergunta": "o que é deriva?",
                                                            "historico": historico}).json()
        self.assertEqual(dados["resposta"], "[fala simulada de mimo-v2.5-pro]")
        self.assertEqual(dados["conceitos"], ["deriva"])
        self.assertEqual(dados["buscas"][0]["documentos"], ["todos"])

        primeira = self.modelo.chamadas[0]
        self.assertFalse(primeira["sem_raciocinio"])
        self.assertEqual([m.papel for m in primeira["mensagens"]], ["system", "user", "assistant", "user"])
        contexto = self.modelo.chamadas[1]["mensagens"][-1].conteudo
        self.assertIn("CONTEXTO DO GRAFO", contexto)
        self.assertIn("deriva drift —causa→ erro de orientação (L1 p.142)", contexto)

    def test_pergunta_vazia(self):
        self.assertEqual(self.cliente.post("/tutor/perguntar", json={"pergunta": " "}).status_code, 400)

    def test_catalogo_grafo_e_trechos(self):
        catalogo = self.cliente.get("/catalogo").json()
        self.assertEqual([(c["id"], c["arquivo"]) for c in catalogo],
                         [("A1", ARTIGO), ("A2", "velocidade2020.pdf"), ("L1", LIVRO)])
        self.assertNotIn("resumo", catalogo[0])
        self.assertEqual(sorted(self.cliente.get("/grafo").json()["nos"]), ["deriva", "erro-orientacao"])

        trechos = self.cliente.get("/trechos", params={"q": "gyro drift", "docs": "L1"}).json()
        self.assertEqual([(t["id"], t["pagina"]) for t in trechos], [("L1", 142)])


class TestSenha(BaseWeb):
    senha = "segredo"

    def test_exige_senha(self):
        self.assertEqual(self.cliente.get("/").status_code, 401)
        self.assertEqual(self.cliente.get("/", auth=("banca", "errada")).status_code, 401)
        self.assertEqual(self.cliente.get("/", auth=("banca", "segredo")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
