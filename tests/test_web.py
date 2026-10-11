import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from sensorchat.container import Container
from sensorchat.domain.conversa import FERRAMENTA
from sensorchat.domain.erros import VozIndisponivel
from sensorchat.infrastructure.configuracao import Configuracao
from sensorchat.interfaces.web.aplicacao import criar_app

from .cenario import ARTIGO, LIVRO, preparar
from .falsos import ModeloFalso, SintetizadorFalso, chamada, fala

PLANO = {"decisoes": ["Usar velocidade relativa"], "abertas": ["Qual erro é tolerável?"], "riscos": ["Deriva do sensor"]}


def roteiro_padrao(modelo, mensagens, ferramentas):
    sistema = mensagens[0].conteudo
    if "grafo de conceitos" in sistema:
        return fala(json.dumps({"entidades": [{"nome": "filtro complementar", "tipo": "metodo"}], "relacoes": []}))
    if mensagens[-1].conteudo.startswith("ARQUIVO") or "exemplo_imu.pdf" in mensagens[-1].conteudo:
        return fala('{"descricao": "Artigo de exemplo.", "resumo": "Filtro complementar (p. 1)."}')
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
        self.voz = SintetizadorFalso()
        self.container = Container(configuracao, self.modelo, vetorizador, avisar=lambda _: None,
                                   sintetizador=self.voz)
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


def pdf_de_exemplo():
    import pymupdf
    paragrafo = ("A complementary filter blends the gyroscope, which is accurate over short intervals, "
                 "with the accelerometer, which gives a drift free inclination reference at rest. ")
    with pymupdf.open() as documento:
        for _ in range(2):
            pagina = documento.new_page()
            for i in range(4):
                pagina.insert_textbox((50, 150 + i * 130, 545, 270 + i * 130), paragrafo * 3, fontsize=9)
        return documento.tobytes()


class TestBiblioteca(BaseWeb):
    def test_pagina_e_estante(self):
        self.assertIn("<title>Biblioteca</title>", self.cliente.get("/biblioteca").text)
        dados = self.cliente.get("/biblioteca/documentos").json()
        self.assertEqual([(d["id"], d["titulo"], d["tem_pdf"]) for d in dados["documentos"]],
                         [("A1", "clemente2021", False), ("A2", "velocidade2020", False), ("L1", "titterton", False)])
        self.assertEqual(dados["documentos"][0]["resumo"], "PUSH Band: SEE 0.135 m/s (p. 7).")
        self.assertEqual(dados["pendentes"], {"artigos": [], "livros": []})
        self.assertEqual(dados["bases"], ["artigos", "livros"])
        self.assertIn("mimo_default", dados["vozes"])

    def test_ler_documento(self):
        aberto = self.cliente.get("/biblioteca/documentos/A1").json()
        self.assertEqual(aberto["arquivo"], ARTIGO)
        self.assertEqual([(b["numero"], b["pagina"]) for b in aberto["blocos"]], [(0, 7), (1, 9)])
        self.assertTrue(aberto["blocos"][0]["texto"].startswith("PUSH Band"))
        self.assertEqual(self.cliente.get("/biblioteca/documentos/Z9").status_code, 404)
        self.assertEqual(self.cliente.get("/biblioteca/documentos/A1/pdf").status_code, 404)

    def test_narrar_guarda_o_audio(self):
        primeira = self.cliente.get("/biblioteca/documentos/A1/audio/0")
        self.assertEqual(primeira.headers["content-type"], "audio/mpeg")
        self.assertTrue(primeira.content.startswith(b"audio:mimo_default:PUSH Band"))
        self.cliente.get("/biblioteca/documentos/A1/audio/0")
        self.assertEqual(len(self.voz.pedidos), 1)
        self.cliente.get("/biblioteca/documentos/A1/audio/0", params={"voz": "Mia"})
        self.assertEqual([voz for _, voz in self.voz.pedidos], ["mimo_default", "Mia"])
        self.assertEqual(len(list((self.raiz / "audio").glob("*.mp3"))), 2)
        self.assertEqual(self.cliente.get("/biblioteca/documentos/A1/audio/7").status_code, 404)
        self.assertEqual(self.cliente.get("/biblioteca/documentos/A1/audio/0", params={"voz": "../x"}).status_code, 502)

    def test_voz_fora_do_ar(self):
        def falhar(texto, voz):
            raise VozIndisponivel("sem saldo")
        self.voz.sintetizar = falhar
        resposta = self.cliente.get("/biblioteca/documentos/A1/audio/0")
        self.assertEqual((resposta.status_code, resposta.json()), (502, {"erro": "sem saldo"}))

    def test_recusa_envios_invalidos(self):
        def enviar(nome, dados, base="artigos"):
            return self.cliente.post("/biblioteca/enviar", params={"base": base, "nome": nome}, content=dados)
        self.assertEqual(enviar("notas.txt", b"%PDF-1.7").status_code, 400)
        self.assertEqual(enviar("falso.pdf", b"<html>").status_code, 400)
        self.assertEqual(enviar("novo.pdf", b"%PDF-1.7", base="revistas").status_code, 400)
        self.assertEqual(enviar(ARTIGO, b"%PDF-1.7").status_code, 409)
        self.assertEqual(enviar("../../fora.pdf", b"%PDF-1.7").json(), {"ok": True, "arquivo": "fora.pdf"})
        self.assertTrue((self.raiz / "pdfs_artigos" / "fora.pdf").exists())
        self.assertFalse((self.raiz.parent / "fora.pdf").exists())
        self.assertEqual(enviar("fora.pdf", b"%PDF-1.7", base="livros").status_code, 409)

    def test_enviar_um_artigo_e_atualizar(self):
        enviado = self.cliente.post("/biblioteca/enviar", params={"base": "artigos", "nome": "exemplo_imu.pdf"},
                                    content=pdf_de_exemplo())
        self.assertEqual(enviado.json(), {"ok": True, "arquivo": "exemplo_imu.pdf"})
        self.assertEqual(self.cliente.get("/biblioteca/documentos").json()["pendentes"]["artigos"], ["exemplo_imu.pdf"])
        self.cliente.get("/catalogo")

        self.assertEqual(self.cliente.post("/biblioteca/atualizar").status_code, 202)
        self.container.atualizacao.aguardar(20)
        estado = self.cliente.get("/biblioteca/atualizacao").json()
        self.assertEqual((estado["ocupada"], estado["erro"], estado["novos"]), (False, "", ["exemplo_imu.pdf"]))
        self.assertTrue(any("exemplo_imu.pdf" in linha for linha in estado["linhas"]))

        estante = self.cliente.get("/biblioteca/documentos").json()
        novo = next(d for d in estante["documentos"] if d["arquivo"] == "exemplo_imu.pdf")
        self.assertEqual((novo["id"], novo["titulo"], novo["tem_pdf"], novo["descricao"]),
                         ("A2", "exemplo imu", True, "Artigo de exemplo."))
        self.assertEqual(estante["pendentes"]["artigos"], [])
        self.assertEqual([d["arquivo"] for d in estante["documentos"]],
                         [ARTIGO, "exemplo_imu.pdf", "velocidade2020.pdf", LIVRO])

        aberto = self.cliente.get("/biblioteca/documentos/exemplo_imu.pdf").json()
        self.assertEqual({b["pagina"] for b in aberto["blocos"]}, {1, 2})
        texto = " ".join(b["texto"] for b in aberto["blocos"])
        self.assertEqual(texto.count("A complementary filter blends"), 24)
        self.assertIn("filtro-complementar", self.cliente.get("/grafo").json()["nos"])
        self.assertIn("deriva", self.cliente.get("/grafo").json()["nos"])
        self.assertEqual(self.cliente.get("/biblioteca/documentos/A2/pdf").headers["content-type"], "application/pdf")

        trechos = self.cliente.get("/trechos", params={"q": "complementary filter gyroscope", "docs": "A2"}).json()
        self.assertEqual({t["arquivo"] for t in trechos}, {"exemplo_imu.pdf"})

        self.cliente.post("/biblioteca/atualizar")
        self.container.atualizacao.aguardar(20)
        self.assertEqual(self.cliente.get("/biblioteca/atualizacao").json()["novos"], [])

    def test_uma_atualizacao_por_vez(self):
        import threading
        solta = threading.Event()
        self.container.atualizar.executar = lambda: solta.wait(5) and []
        self.assertEqual(self.cliente.post("/biblioteca/atualizar").status_code, 202)
        self.assertEqual(self.cliente.post("/biblioteca/atualizar").status_code, 409)
        self.assertTrue(self.cliente.get("/biblioteca/atualizacao").json()["ocupada"])
        solta.set()
        self.container.atualizacao.aguardar(5)
        self.assertFalse(self.cliente.get("/biblioteca/atualizacao").json()["ocupada"])


class TestSenha(BaseWeb):
    senha = "segredo"

    def test_exige_senha(self):
        self.assertEqual(self.cliente.get("/").status_code, 401)
        self.assertEqual(self.cliente.get("/", auth=("banca", "errada")).status_code, 401)
        self.assertEqual(self.cliente.get("/", auth=("banca", "segredo")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
