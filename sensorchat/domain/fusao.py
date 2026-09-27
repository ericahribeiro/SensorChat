import re
import unicodedata
from dataclasses import dataclass

import numpy as np

from .grafo import Aresta, No

LIMIAR_FUSAO = 0.96
PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "com", "para", "por", "em", "the", "of"}


def slug(nome):
    ascii_ = unicodedata.normalize("NFKD", nome.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:60]


def partes(nome):
    fora = re.sub(r"\(.*?\)", " ", nome).strip()
    dentro = re.findall(r"\((.*?)\)", nome)
    sigla = slug(dentro[0]) if dentro else None
    tokens = {t.rstrip("s") for t in slug(fora).split("-")
              if len(t) >= 4 and t not in PALAVRAS_VAZIAS}
    return slug(fora), sigla, tokens


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else ""


@dataclass(frozen=True)
class EntidadeExtraida:
    nome: str
    tipo: str
    descricao: str

    @classmethod
    def de_dict(cls, dados):
        return cls(_texto(dados.get("nome")), _texto(dados.get("tipo")) or "conceito",
                   _texto(dados.get("descricao")))


@dataclass(frozen=True)
class RelacaoExtraida:
    de: str
    para: str
    relacao: str

    @classmethod
    def de_dict(cls, dados):
        return cls(_texto(dados.get("de")).lower(), _texto(dados.get("para")).lower(),
                   _texto(dados.get("relacao")).lower())


class FusorDeConceitos:
    def __init__(self, grafo):
        self.grafo = grafo
        self._ids = list(grafo.nos)
        self._por_chave, self._por_sigla, self._tokens, self._siglas = {}, {}, {}, {}
        for nid, no in grafo.nos.items():
            for nome in [no.nome, *no.apelidos]:
                self._registrar(nid, nome)

    def incorporar(self, entidades, relacoes, origem, vetores):
        mapa = {}
        for entidade, vetor in zip(entidades, vetores):
            alvo = self._achar(entidade.nome, vetor) or self._criar(entidade, vetor)
            self._registrar(alvo, entidade.nome)
            self._completar(self.grafo.nos[alvo], entidade, origem)
            mapa[entidade.nome.lower()] = alvo
        self._ligar(relacoes, mapa, origem)

    def _registrar(self, nid, nome):
        chave, sigla, tokens = partes(nome)
        self._por_chave.setdefault(chave, nid)
        if sigla:
            self._por_sigla.setdefault(sigla, nid)
            self._siglas.setdefault(nid, set()).add(sigla)
        if tokens:
            self._tokens.setdefault(nid, []).append(tokens)

    def _achar(self, nome, vetor):
        chave, sigla, tokens = partes(nome)
        if chave in self._por_chave:
            return self._por_chave[chave]
        if sigla and sigla in self._por_sigla:
            return self._por_sigla[sigla]
        if not self._ids or not tokens:
            return None
        notas = self.grafo.vetores @ vetor
        for j in np.argsort(-notas)[:5]:
            if notas[j] < LIMIAR_FUSAO:
                break
            nid = self._ids[j]
            if sigla and self._siglas.get(nid) and sigla not in self._siglas[nid]:
                continue
            if any(tokens <= outros or outros <= tokens for outros in self._tokens.get(nid, [])):
                return nid
        return None

    def _criar(self, entidade, vetor):
        alvo = slug(entidade.nome) or f"no-{len(self._ids)}"
        while alvo in self.grafo.nos:
            alvo += "-"
        self.grafo.nos[alvo] = No(entidade.nome, entidade.tipo, entidade.descricao)
        self._ids.append(alvo)
        vetores = self.grafo.vetores
        self.grafo.vetores = vetor[None] if not len(vetores) else np.vstack([vetores, vetor[None]])
        return alvo

    def _completar(self, no, entidade, origem):
        if entidade.nome != no.nome and entidade.nome not in no.apelidos:
            no.apelidos.append(entidade.nome)
        if not no.descricao and entidade.descricao:
            no.descricao = entidade.descricao
        no.registrar_origem(origem)

    def _ligar(self, relacoes, mapa, origem):
        existentes = {a.chave: a for a in self.grafo.arestas}
        for relacao in relacoes:
            de, para = mapa.get(relacao.de), mapa.get(relacao.para)
            if not de or not para or de == para or not relacao.relacao:
                continue
            chave = (de, para, relacao.relacao)
            if chave in existentes:
                existentes[chave].registrar_origem(origem)
                continue
            aresta = Aresta(de, para, relacao.relacao, [origem])
            self.grafo.arestas.append(aresta)
            existentes[chave] = aresta
