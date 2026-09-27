import logging

from ..domain.busca import ResultadoBusca, buscar_na_selecao, combinar_por_cotas
from ..domain.documentos import Catalogo
from ..domain.erros import BaseInexistente, NenhumaBaseDisponivel
from .registro import resumir

COTAS_PADRAO = {"artigos": 3, "livros": 3}

log = logging.getLogger(__name__)


class ServicoBusca:
    def __init__(self, bases, catalogo, vetorizador):
        self._bases = bases
        self._catalogo = catalogo
        self._vetorizador = vetorizador
        self._carregadas = {}
        self._ausentes = set()

    def nomes(self):
        return self._bases.nomes()

    def base(self, nome):
        if nome not in self._carregadas:
            try:
                base = self._bases.carregar(nome)
            except BaseInexistente:
                if nome not in self._ausentes:
                    log.warning("base '%s' não existe; ela fica fora das buscas", nome)
                    self._ausentes.add(nome)
                return None
            self._ausentes.discard(nome)
            self._carregadas[nome] = base
            log.info("base '%s' carregada: %d pedaços de %d arquivos",
                     nome, len(base.pedacos), len(base.contagem_por_arquivo()))
        return self._carregadas[nome]

    def disponiveis(self, nomes=None):
        return [base for nome in (nomes or self.nomes()) if (base := self.base(nome)) is not None]

    def catalogo(self):
        return Catalogo.montar(self.disponiveis(), self._catalogo.descricoes())

    def buscar_por_cotas(self, pergunta, cotas=None, total=6):
        cotas = cotas or COTAS_PADRAO
        bases = self.disponiveis(list(cotas))
        if not bases:
            raise NenhumaBaseDisponivel()
        log.info("busca por cotas %s: «%s»", cotas, resumir(pergunta))
        vetor = self._vetorizador.vetorizar_pergunta(pergunta)
        candidatos = {base.nome: base.melhores(vetor, total) for base in bases}
        trechos = combinar_por_cotas(candidatos, cotas, total)
        log.info("busca por cotas devolveu %d trechos: %s", len(trechos), _resumo(trechos))
        return trechos

    def buscar_em(self, pergunta, documentos=None, total=6, fora=2):
        bases = self.disponiveis()
        if not bases:
            raise NenhumaBaseDisponivel()
        selecao = self.catalogo().selecionar(documentos)
        alvo = ", ".join(documentos) if documentos else "todos"
        log.info("buscando em [%s]: «%s»", alvo, resumir(pergunta))
        if selecao.nao_encontrados:
            log.warning("documentos não reconhecidos no catálogo: %s", ", ".join(selecao.nao_encontrados))
        vetor = self._vetorizador.vetorizar_pergunta(pergunta)
        dentro, restante = buscar_na_selecao(bases, vetor, selecao.arquivos, total, fora)
        log.info("busca devolveu %d trechos da seleção (%s) e %d melhores de fora",
                 len(dentro), _resumo(dentro), len(restante))
        return ResultadoBusca(dentro, restante, selecao.nao_encontrados)


def _resumo(trechos):
    if not trechos:
        return "nenhum"
    return f"notas {trechos[-1].nota:.3f} a {trechos[0].nota:.3f}"
