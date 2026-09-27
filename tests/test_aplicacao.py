import json
import tempfile
import unittest
from pathlib import Path

from sensorchat.container import Container
from sensorchat.domain.conversa import USUARIO, Mensagem
from sensorchat.domain.limpeza import Bloco, PaginaBruta
from sensorchat.infrastructure.configuracao import Configuracao

from .cenario import ARTIGO, preparar
from .falsos import ModeloFalso, VetorizadorFalso, chamada, fala

PARAGRAFO = ("The gyroscope measures angular rate about each body axis, and integrating this "
             "signal yields orientation that slowly drifts because of residual bias. ")


class FonteFalsa:
    def __init__(self, documentos):
        self._documentos = documentos

    def local(self, base):
        return f"pdfs_{base}"

    def listar(self, base):
        return sorted(self._documentos)

    def ler(self, caminho):
        if self._documentos[caminho] is None:
            raise RuntimeError("PDF corrompido")
        return self._documentos[caminho]


def _pagina(numero, texto):
    return PaginaBruta(numero, (Bloco(texto, 300, 600, 1000),))


def _container(raiz, roteiro, vetorizador=None, fonte=None, avisar=lambda _: None):
    return Container(Configuracao(raiz=raiz, api_key="falsa"), ModeloFalso(roteiro),
                     vetorizador or VetorizadorFalso(), fonte, avisar)


class ComRaiz(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class TestRoteador(ComRaiz):
    def setUp(self):
        super().setUp()
        self.vetorizador = preparar(self.raiz)

    def test_busca_cega_quando_o_modelo_nao_busca(self):
        container = _container(self.raiz, lambda *_: fala("resposta"), self.vetorizador)
        resposta, consultas = container.roteador.responder(
            "m", [Mensagem.sistema("s"), Mensagem.usuario("velocity")], 100, busca_cega="bench press velocity")
        self.assertEqual([c.ferramenta for c in consultas], ["busca_cega"])
        ultima = container.modelo_linguagem.chamadas[-1]["mensagens"][-1]
        self.assertEqual(ultima.papel, USUARIO)
        self.assertTrue(ultima.conteudo.startswith("Você não consultou a base."))
        self.assertEqual(len(container.modelo_linguagem.chamadas), 2)

    def test_forca_a_fala_depois_do_limite_de_rodadas(self):
        container = _container(self.raiz, lambda m, msgs, ferramentas: chamada(
            "ler_resumo", {"documento": "A1"}) if ferramentas else fala("enfim"), self.vetorizador)
        resposta, consultas = container.roteador.responder("m", [Mensagem.sistema("s")], 100)
        self.assertEqual(resposta.texto, "enfim")
        self.assertEqual(len(consultas), 4)
        self.assertEqual(consultas[0].arquivos, (ARTIGO,))

    def test_ferramentas(self):
        roteador = _container(self.raiz, lambda *_: fala(""), self.vetorizador).roteador
        self.assertIn("0.135", roteador.executar("ler_resumo", {"documento": "A1"})[0])
        self.assertIn("ainda não tem resumo", roteador.executar("ler_resumo", {"documento": "L1"})[0])
        self.assertIn("não reconhecido", roteador.executar("ler_resumo", {"documento": "Z9"})[0])
        self.assertIn("desconhecida", roteador.executar("apagar_tudo", {})[0])

        texto, _ = roteador.executar("buscar_na_base", {"documentos": ["A1", "Z9"],
                                                        "pergunta": "gyro bias drift angle error"})
        self.assertIn("Não reconheci: Z9", texto)
        self.assertIn("FORA DA SELEÇÃO", texto)

    def test_sem_bases(self):
        roteador = _container(self.raiz / "vazio", lambda *_: fala("")).roteador
        self.assertIn("vazio", roteador.bloco_catalogo())
        self.assertIn("Nenhuma base", roteador.executar("buscar_na_base", {"pergunta": "x"})[0])


class TestPipeline(ComRaiz):
    def test_indexar_descrever_extrair_e_refundir(self):
        documentos = {
            "a.pdf": [_pagina(n, "\n\n".join([PARAGRAFO * 2] * 4)) for n in range(1, 4)],
            "escaneado.pdf": [_pagina(1, "")],
            "quebrado.pdf": None,
        }
        avisos = []

        def roteiro(modelo, mensagens, ferramentas):
            if "grafo de conceitos" in mensagens[0].conteudo:
                return fala(json.dumps({
                    "entidades": [{"nome": "giroscópio (gyroscope)", "tipo": "dispositivo"},
                                  {"nome": "deriva (drift)", "tipo": "fenomeno"}],
                    "relacoes": [{"de": "giroscópio (gyroscope)", "para": "deriva (drift)", "relacao": "sofre"}]}))
            return fala('{"descricao": " Artigo de método. ", "resumo": "Deriva (p. 1)."}')

        container = _container(self.raiz, roteiro, fonte=FonteFalsa(documentos), avisar=avisos.append)

        self.assertGreater(container.indexar.executar("artigos"), 0)
        self.assertTrue(any("FALHOU quebrado.pdf" in a for a in avisos))
        self.assertTrue(any("AVISO escaneado.pdf" in a for a in avisos))
        self.assertTrue((self.raiz / "base_artigos.npz").exists())

        self.assertEqual(container.descrever.executar(), 1)
        catalogo = json.loads((self.raiz / "catalogo.json").read_text(encoding="utf-8"))
        self.assertEqual(catalogo, [{"arquivo": "a.pdf", "base": "artigos",
                                     "descricao": "Artigo de método.", "resumo": "Deriva (p. 1)."}])
        self.assertEqual(container.descrever.executar(), 0)

        grafo = container.extrair.executar("resumos")
        self.assertEqual(sorted(grafo.nos), ["deriva-drift", "giroscopio-gyroscope"])
        self.assertEqual(len(grafo.arestas), 1)
        extracoes = json.loads((self.raiz / "extracoes.json").read_text(encoding="utf-8"))
        self.assertEqual(list(extracoes), ['{"arquivo": "a.pdf", "pagina": null}'])

        chamadas_antes = len(container.modelo_linguagem.chamadas)
        container.extrair.executar("resumos")
        self.assertEqual(len(container.modelo_linguagem.chamadas), chamadas_antes)

        refundido = container.extrair.refundir()
        self.assertEqual(refundido.como_dict(), grafo.como_dict())


if __name__ == "__main__":
    unittest.main()
