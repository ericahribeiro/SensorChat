from functools import cached_property

from .application.banca import Banca
from .application.busca import ServicoBusca
from .application.descricao import DescreverDocumentos
from .application.extracao import ExtrairGrafo
from .application.grafo import ConsultaGrafo
from .application.indexacao import IndexarBase
from .application.roteamento import RoteadorDeBusca
from .application.tutor import Tutor
from .infrastructure.fonte_pdf import FontePdfLocal
from .infrastructure.modelo_openai import ModeloOpenAI
from .infrastructure.persistencia.ata import RepositorioAtaEmArquivo
from .infrastructure.persistencia.bases import RepositorioBasesEmArquivo
from .infrastructure.persistencia.catalogo import RepositorioCatalogoEmArquivo
from .infrastructure.persistencia.extracoes import RepositorioExtracoesEmArquivo
from .infrastructure.persistencia.grafo import RepositorioGrafoEmArquivo
from .infrastructure.publicador_html import PublicadorHtml
from .infrastructure.vetorizador import VetorizadorE5


class Container:
    def __init__(self, configuracao, modelo_linguagem=None, vetorizador=None, fonte=None, avisar=print):
        self.configuracao = configuracao
        self.avisar = avisar
        self._modelo_linguagem = modelo_linguagem
        self._vetorizador = vetorizador
        self._fonte = fonte

    @property
    def raiz(self):
        return self.configuracao.raiz

    @cached_property
    def modelo_linguagem(self):
        return self._modelo_linguagem or ModeloOpenAI.conectar(self.configuracao)

    @cached_property
    def vetorizador(self):
        return self._vetorizador or VetorizadorE5()

    @cached_property
    def bases(self):
        return RepositorioBasesEmArquivo(self.raiz)

    @cached_property
    def catalogo(self):
        return RepositorioCatalogoEmArquivo(self.raiz / "catalogo.json")

    @cached_property
    def grafos(self):
        return RepositorioGrafoEmArquivo(self.raiz / "grafo.json", self.raiz / "grafo.npz")

    @cached_property
    def extracoes(self):
        return RepositorioExtracoesEmArquivo(self.raiz / "extracoes.json")

    @cached_property
    def atas(self):
        return RepositorioAtaEmArquivo(self.raiz / "ata.json")

    @cached_property
    def publicador(self):
        return PublicadorHtml(self.raiz / "publico")

    @cached_property
    def fonte(self):
        return self._fonte or FontePdfLocal(self.raiz)

    @cached_property
    def busca(self):
        return ServicoBusca(self.bases, self.catalogo, self.vetorizador)

    @cached_property
    def consulta_grafo(self):
        return ConsultaGrafo(self.grafos, self.vetorizador)

    @cached_property
    def roteador(self):
        return RoteadorDeBusca(self.modelo_linguagem, self.busca, self.consulta_grafo)

    @cached_property
    def tutor(self):
        return Tutor(self.roteador)

    @cached_property
    def banca(self):
        return Banca(self.atas, self.modelo_linguagem, self.roteador, self.publicador)

    @cached_property
    def indexar(self):
        return IndexarBase(self.fonte, self.bases, self.vetorizador, self.avisar)

    @cached_property
    def descrever(self):
        return DescreverDocumentos(self.busca, self.catalogo, self.modelo_linguagem, self.avisar)

    @cached_property
    def extrair(self):
        return ExtrairGrafo(self.bases, self.catalogo, self.grafos, self.extracoes,
                            self.vetorizador, self.modelo_linguagem, self.avisar)
