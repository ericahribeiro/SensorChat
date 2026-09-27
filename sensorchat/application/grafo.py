import logging

log = logging.getLogger(__name__)


class ConsultaGrafo:
    def __init__(self, repositorio, vetorizador):
        self._repositorio = repositorio
        self._vetorizador = vetorizador

    def grafo(self):
        return self._repositorio.carregar()

    def contexto(self, pergunta, catalogo, documentos=None):
        grafo = self.grafo()
        if grafo is None or grafo.vazio:
            log.info("grafo de conceitos vazio; a busca segue sem contexto do grafo")
            return "", []
        arquivos = catalogo.selecionar(documentos).arquivos if documentos else None
        vetor = self._vetorizador.vetorizar_pergunta(pergunta)
        centrais, arestas = grafo.consultar(vetor, arquivos)
        if centrais:
            log.info("grafo: %d conceitos ligados à pergunta (%s) e %d relações",
                     len(centrais), ", ".join(grafo.nos[c].nome for c in centrais), len(arestas))
        else:
            log.info("grafo: nenhum conceito passou do limiar de similaridade")
        return grafo.formatar(centrais, arestas, catalogo.ids_por_arquivo()), centrais
