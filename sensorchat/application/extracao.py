from ..domain.conversa import Mensagem
from ..domain.erros import CatalogoAusente
from ..domain.fusao import EntidadeExtraida, FusorDeConceitos, RelacaoExtraida
from ..domain.grafo import GrafoConceitos, Origem
from . import instrucoes
from .json_modelo import ler_json

MODELO = "mimo-v2.5"
MAX_TOKENS = 1500
SALVAR_A_CADA = 20
LOTE_VETORIZACAO = 64
RESUMOS = "resumos"
TRECHOS = "trechos"


class ExtrairGrafo:
    def __init__(self, bases, catalogo, grafos, extracoes, vetorizador, modelo_linguagem, avisar=print):
        self._bases = bases
        self._catalogo = catalogo
        self._grafos = grafos
        self._extracoes = extracoes
        self._vetorizador = vetorizador
        self._modelo = modelo_linguagem
        self._avisar = avisar

    def refundir(self):
        cache = self._extracoes.carregar()
        fusor = FusorDeConceitos(GrafoConceitos())
        for item in cache.values():
            self._incorporar(fusor, item["entidades"], item["relacoes"], Origem.de_dict(item["origem"]))
        self._grafos.salvar(fusor.grafo)
        self._avisar(f"refundido do cache: {len(cache)} textos -> {self._tamanho(fusor.grafo)}")
        return fusor.grafo

    def executar(self, fonte, base=None, filtro=None, zerar=False):
        textos = list(self._textos(fonte, base, filtro.lower() if filtro else None))
        cache = self._extracoes.carregar()
        existente = None if zerar else self._grafos.carregar()
        fusor = FusorDeConceitos(existente or GrafoConceitos())
        feitos_antes = fusor.grafo.origens_registradas()

        extraidos, falhas = 0, 0
        for texto, origem in textos:
            chave = origem.chave()
            if chave in feitos_antes:
                continue
            try:
                if chave not in cache:
                    entidades, relacoes = self._extrair(texto)
                    cache[chave] = {"origem": origem.como_dict(), "entidades": entidades, "relacoes": relacoes}
                item = cache[chave]
                self._incorporar(fusor, item["entidades"], item["relacoes"], origem)
            except Exception as erro:
                falhas += 1
                self._avisar(f"  FALHOU {origem.arquivo[:44]}: {str(erro)[:100]}")
                continue
            extraidos += 1
            rotulo = origem.arquivo[:44] + (f" p.{origem.pagina}" if origem.pagina else "")
            self._avisar(f"  {rotulo}: {len(item['entidades'])} ent, {len(item['relacoes'])} rel | "
                         f"grafo: {self._tamanho(fusor.grafo)}")
            if extraidos % SALVAR_A_CADA == 0:
                self._salvar(fusor.grafo, cache)

        self._salvar(fusor.grafo, cache)
        self._avisar(f"\n{extraidos} textos extraídos ({falhas} falhas) -> {self._tamanho(fusor.grafo)}")
        return fusor.grafo

    def _textos(self, fonte, base, filtro):
        if fonte == RESUMOS:
            descricoes = self._catalogo.descricoes()
            if not descricoes:
                raise CatalogoAusente()
            for descricao in descricoes.values():
                if filtro and filtro not in descricao.arquivo.lower():
                    continue
                if descricao.resumo:
                    yield descricao.resumo, Origem(descricao.arquivo, None)
        elif fonte == TRECHOS:
            for pedaco in self._bases.carregar(base).pedacos:
                if filtro and filtro not in pedaco.arquivo.lower():
                    continue
                yield pedaco.texto, Origem(pedaco.arquivo, pedaco.pagina)
        else:
            raise ValueError(f"Fonte: {RESUMOS} | {TRECHOS} <base>")

    def _extrair(self, texto):
        resposta = self._modelo.completar(
            MODELO, [Mensagem.sistema(instrucoes.EXTRAIR), Mensagem.usuario(texto)],
            MAX_TOKENS, sem_raciocinio=True)
        dados = ler_json(resposta.texto)
        return dados.get("entidades", []), dados.get("relacoes", [])

    def _incorporar(self, fusor, entidades, relacoes, origem):
        entidades = [EntidadeExtraida.de_dict(e) for e in entidades if isinstance(e, dict)]
        entidades = [e for e in entidades if e.nome]
        if not entidades:
            return
        relacoes = [RelacaoExtraida.de_dict(r) for r in relacoes if isinstance(r, dict)]
        vetores = self._vetorizador.vetorizar_documentos([e.nome for e in entidades], lote=LOTE_VETORIZACAO)
        fusor.incorporar(entidades, relacoes, origem, vetores)

    def _salvar(self, grafo, cache):
        self._grafos.salvar(grafo)
        self._extracoes.salvar(cache)

    @staticmethod
    def _tamanho(grafo):
        return f"{len(grafo.nos)} nós, {len(grafo.arestas)} arestas"
