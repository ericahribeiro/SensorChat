import unittest

import numpy as np

from sensorchat.domain.ata import AGENTE, HUMANO, Ata, Plano
from sensorchat.domain.busca import buscar_na_selecao, combinar_por_cotas
from sensorchat.domain.conversa import Consulta, RespostaModelo
from sensorchat.domain.documentos import BaseVetorial, Catalogo, Descricao, Pedaco, Trecho
from sensorchat.domain.fatiamento import MIN_PEDACO, picar
from sensorchat.domain.fusao import EntidadeExtraida, FusorDeConceitos, RelacaoExtraida, partes
from sensorchat.domain.grafo import GrafoConceitos, Origem
from sensorchat.domain.limpeza import Bloco, Pagina, PaginaBruta, cortar_referencias, limpar_paginas
from sensorchat.domain.prosa import classificar


def _base(nome, arquivos):
    pedacos = [Pedaco(a, 1, f"texto {i}") for i, a in enumerate(arquivos)]
    vetores = np.eye(len(arquivos), dtype="float32")
    return BaseVetorial(nome, vetores, pedacos)


class TestLimpeza(unittest.TestCase):
    def test_remove_cabecalho_repetido_na_borda(self):
        paginas = [PaginaBruta(n, (Bloco("Journal of Sensors 2021", 5, 20, 1000),
                                   Bloco(f"Conteúdo único da página {n} " * 8, 300, 600, 1000)))
                   for n in range(1, 6)]
        limpas, lixo = limpar_paginas(paginas)
        self.assertTrue(lixo)
        self.assertTrue(all("Journal" not in p.texto for p in limpas))
        self.assertTrue(all("Conteúdo único" in p.texto for p in limpas))

    def test_corta_referencias_no_fim(self):
        paginas = [Pagina(i, f"texto {i}") for i in range(1, 5)] + [Pagina(5, "fim\nReferences\n[1] A. B.")]
        cortadas, pagina = cortar_referencias(paginas)
        self.assertEqual(pagina, 5)
        self.assertEqual(cortadas[-1].texto, "fim\n")

    def test_nao_corta_referencias_no_comeco(self):
        paginas = [Pagina(1, "References\nx")] + [Pagina(i, "texto") for i in range(2, 6)]
        self.assertEqual(cortar_referencias(paginas), (paginas, None))


class TestFatiamento(unittest.TestCase):
    def test_pedacos_respeitam_tamanho_minimo_e_pagina(self):
        paragrafo = "O giroscópio mede velocidade angular em torno de cada eixo do corpo. " * 4
        pedacos = picar([Pagina(3, "\n\n".join([paragrafo] * 5))], "a.pdf")
        self.assertTrue(pedacos)
        self.assertTrue(all(len(p.texto) >= MIN_PEDACO and p.pagina == 3 for p in pedacos))


class TestProsa(unittest.TestCase):
    def test_detecta_sumario(self):
        self.assertEqual(classificar("Capítulo 1 ........ 3\nCapítulo 2 ........ 9"), "sumário")

    def test_aceita_prosa(self):
        texto = ("The gyroscope measures angular rate about each body axis, and integrating this "
                 "signal yields orientation that slowly drifts because of residual bias. ") * 3
        self.assertIsNone(classificar(texto))


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.catalogo = Catalogo.montar(
            [_base("artigos", ["b.pdf", "a.pdf"]), _base("livros", ["livro.pdf"])],
            {"a.pdf": Descricao("a.pdf", "artigos", "desc A", "resumo A")})

    def test_ids_seguem_ordem_alfabetica_por_base(self):
        self.assertEqual([(d.id, d.arquivo) for d in self.catalogo],
                         [("A1", "a.pdf"), ("A2", "b.pdf"), ("L1", "livro.pdf")])

    def test_resolver_por_id_arquivo_e_trecho_unico(self):
        self.assertEqual(self.catalogo.resolver("a2").arquivo, "b.pdf")
        self.assertEqual(self.catalogo.resolver("LIVRO.PDF").id, "L1")
        self.assertEqual(self.catalogo.resolver("livro").id, "L1")
        self.assertIsNone(self.catalogo.resolver(".pdf"))

    def test_selecionar(self):
        selecao = self.catalogo.selecionar(["A1", "Z9"])
        self.assertEqual(selecao.arquivos, frozenset({"a.pdf"}))
        self.assertEqual(selecao.nao_encontrados, ("Z9",))
        self.assertIsNone(self.catalogo.selecionar(["todos"]).arquivos)
        self.assertIsNone(self.catalogo.selecionar(["Z9"]).arquivos)


class TestBusca(unittest.TestCase):
    def test_cotas_garantem_espaco_para_cada_base(self):
        trechos = lambda base, notas: [Trecho(n, Pedaco("x", 1, "t"), base) for n in notas]
        escolhidos = combinar_por_cotas({"artigos": trechos("artigos", [0.9, 0.8, 0.7]),
                                         "livros": trechos("livros", [0.3, 0.2])},
                                        {"artigos": 1, "livros": 1}, 3)
        self.assertEqual([t.nota for t in escolhidos], [0.9, 0.8, 0.3])

    def test_fora_da_selecao_so_quando_supera_o_melhor_de_dentro(self):
        base = _base("artigos", ["a.pdf", "b.pdf", "c.pdf"])
        vetor = np.array([0.5, 0.9, 0.1], dtype="float32")
        dentro, fora = buscar_na_selecao([base], vetor, frozenset({"a.pdf"}), 6, 2)
        self.assertEqual([t.pedaco.arquivo for t in dentro], ["a.pdf"])
        self.assertEqual([t.pedaco.arquivo for t in fora], ["b.pdf"])


class TestGrafo(unittest.TestCase):
    def test_fusao_por_sigla_e_consulta(self):
        fusor = FusorDeConceitos(GrafoConceitos())
        vetores = np.eye(3, dtype="float32")
        fusor.incorporar(
            [EntidadeExtraida("unidade de medição inercial (IMU)", "dispositivo", ""),
             EntidadeExtraida("deriva (drift)", "fenomeno", "erro que cresce"),
             EntidadeExtraida("sensor inercial (IMU)", "dispositivo", "mede aceleração")],
            [RelacaoExtraida("deriva (drift)", "unidade de medição inercial (imu)", "limita")],
            Origem("a.pdf", 2), vetores)
        grafo = fusor.grafo
        self.assertEqual(len(grafo.nos), 2)
        imu = grafo.nos["unidade-de-medicao-inercial-imu"]
        self.assertIn("sensor inercial (IMU)", imu.apelidos)
        self.assertEqual(imu.descricao, "mede aceleração")
        self.assertEqual(len(grafo.arestas), 1)

        centrais, arestas = grafo.consultar(vetores[1], frozenset({"a.pdf"}))
        self.assertEqual(centrais, ["deriva-drift"])
        texto = grafo.formatar(centrais, arestas, {"a.pdf": "A1"})
        self.assertIn("deriva (drift) [fenomeno] — erro que cresce (A1 p.2)", texto)
        self.assertIn("—limita→", texto)
        self.assertEqual(grafo.consultar(vetores[1], frozenset({"outro.pdf"})), ([], []))

    def test_partes_do_nome(self):
        self.assertEqual(partes("Deriva do Giroscópio (Gyro Drift)"),
                         ("deriva-do-giroscopio", "gyro-drift", {"deriva", "giroscopio"}))


class TestAta(unittest.TestCase):
    def test_ida_e_volta_preserva_formato(self):
        ata = Ata()
        ata.acrescentar("Érica", HUMANO, "  oi  ", "2026-09-26T10:00:00")
        ata.acrescentar("Especialista", AGENTE, "fala", "2026-09-26T10:01:00",
                        [Consulta("busca_cega", ("todos",), ("todos",), "oi")])
        ata.definir_plano(Plano.de_dict({"decisoes": ["x"], "abertas": "não é lista"}))
        dados = ata.como_dict()
        self.assertEqual(dados["linhas"][0], {"n": 0, "autor": "Érica", "papel": "humano",
                                              "texto": "oi", "quando": "2026-09-26T10:00:00"})
        self.assertNotIn("conceitos", dados["linhas"][1]["buscas"][0])
        self.assertEqual(dados["plano"], {"decisoes": ["x"], "abertas": [], "riscos": []})
        self.assertEqual(Ata.de_dict(dados).como_dict(), dados)
        self.assertEqual(ata.ultima_fala_humana(), "oi")

    def test_texto_completo_avisa_interrupcao(self):
        self.assertIn("interrompida", RespostaModelo("meia fala", interrompida=True).texto_completo())
        self.assertIn("interrompida", RespostaModelo("  ").texto_completo())
        self.assertEqual(RespostaModelo(" ok ").texto_completo(), "ok")


if __name__ == "__main__":
    unittest.main()
