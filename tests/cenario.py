from sensorchat.domain.documentos import Descricao, Pedaco
from sensorchat.domain.grafo import Aresta, GrafoConceitos, No, Origem
from sensorchat.infrastructure.persistencia.bases import RepositorioBasesEmArquivo
from sensorchat.infrastructure.persistencia.catalogo import RepositorioCatalogoEmArquivo
from sensorchat.infrastructure.persistencia.grafo import RepositorioGrafoEmArquivo

from .falsos import VetorizadorFalso

ARTIGO = "clemente2021.pdf"
OUTRO_ARTIGO = "velocidade2020.pdf"
LIVRO = "titterton.pdf"

PEDACOS_ARTIGOS = [
    Pedaco(ARTIGO, 7, "PUSH Band standard error of estimate 0.135 m/s for bench press velocity"),
    Pedaco(ARTIGO, 9, "Linear position transducers remain the criterion device for barbell velocity"),
    Pedaco(OUTRO_ARTIGO, 3, "Mean concentric velocity decreases linearly with relative load"),
]
PEDACOS_LIVROS = [
    Pedaco(LIVRO, 142, "Gyro bias integrates into a linearly growing angle error called drift"),
]


def preparar(raiz):
    vetorizador = VetorizadorFalso()
    bases = RepositorioBasesEmArquivo(raiz)
    for nome, pedacos in (("artigos", PEDACOS_ARTIGOS), ("livros", PEDACOS_LIVROS)):
        bases.salvar(nome, vetorizador.vetorizar_documentos([p.texto for p in pedacos]), pedacos)

    RepositorioCatalogoEmArquivo(raiz / "catalogo.json").salvar([
        Descricao(ARTIGO, "artigos", "Revisão de validade de dispositivos de VBT.", "PUSH Band: SEE 0.135 m/s (p. 7)."),
        Descricao(LIVRO, "livros", "Livro-texto de navegação inercial.", ""),
    ])

    nomes = ["deriva drift", "erro de orientação"]
    grafo = GrafoConceitos(
        nos={
            "deriva": No("deriva drift", "fenomeno", "erro que cresce", [], [Origem(LIVRO, 142)]),
            "erro-orientacao": No("erro de orientação", "grandeza", "", [], [Origem(ARTIGO, None)]),
        },
        arestas=[Aresta("deriva", "erro-orientacao", "causa", [Origem(LIVRO, 142)])],
        vetores=vetorizador.vetorizar_documentos(nomes),
    )
    RepositorioGrafoEmArquivo(raiz / "grafo.json", raiz / "grafo.npz").salvar(grafo)
    return vetorizador
