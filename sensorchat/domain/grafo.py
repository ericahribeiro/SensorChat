import json
from dataclasses import dataclass, field

import numpy as np

LIMIAR_PERGUNTA = 0.80


@dataclass(frozen=True)
class Origem:
    arquivo: str
    pagina: int | None = None

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["arquivo"], dados.get("pagina"))

    def como_dict(self):
        return {"arquivo": self.arquivo, "pagina": self.pagina}

    def chave(self):
        return json.dumps(self.como_dict(), sort_keys=True)

    def rotulo(self, ids_por_arquivo):
        rotulo = ids_por_arquivo.get(self.arquivo, self.arquivo[:20])
        return rotulo + (f" p.{self.pagina}" if self.pagina else "")


def _rotulos(origens, ids_por_arquivo):
    vistos = []
    for origem in origens:
        rotulo = origem.rotulo(ids_por_arquivo)
        if rotulo not in vistos:
            vistos.append(rotulo)
    return ", ".join(vistos[:3])


@dataclass
class No:
    nome: str
    tipo: str = "conceito"
    descricao: str = ""
    apelidos: list = field(default_factory=list)
    origens: list = field(default_factory=list)

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["nome"], dados.get("tipo", "?"), dados.get("descricao", ""),
                   list(dados.get("apelidos", [])),
                   [Origem.de_dict(o) for o in dados.get("origens", [])])

    def como_dict(self):
        return {"nome": self.nome, "tipo": self.tipo, "descricao": self.descricao,
                "apelidos": list(self.apelidos), "origens": [o.como_dict() for o in self.origens]}

    def arquivos(self):
        return {o.arquivo for o in self.origens}

    def registrar_origem(self, origem):
        if origem not in self.origens:
            self.origens.append(origem)


@dataclass
class Aresta:
    de: str
    para: str
    relacao: str
    origens: list = field(default_factory=list)

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["de"], dados["para"], dados["relacao"],
                   [Origem.de_dict(o) for o in dados.get("origens", [])])

    def como_dict(self):
        return {"de": self.de, "para": self.para, "relacao": self.relacao,
                "origens": [o.como_dict() for o in self.origens]}

    @property
    def chave(self):
        return self.de, self.para, self.relacao

    def arquivos(self):
        return {o.arquivo for o in self.origens}

    def registrar_origem(self, origem):
        if origem not in self.origens:
            self.origens.append(origem)


class GrafoConceitos:
    def __init__(self, nos=None, arestas=None, vetores=None):
        self.nos = dict(nos or {})
        self.arestas = list(arestas or [])
        self.vetores = vetores if vetores is not None else np.zeros((0, 0), "float32")

    @classmethod
    def de_dict(cls, dados, vetores):
        nos = {nid: No.de_dict(no) for nid, no in dados.get("nos", {}).items()}
        arestas = [Aresta.de_dict(a) for a in dados.get("arestas", [])]
        return cls(nos, arestas, vetores)

    def como_dict(self):
        return {"nos": {nid: no.como_dict() for nid, no in self.nos.items()},
                "arestas": [a.como_dict() for a in self.arestas]}

    @property
    def vazio(self):
        return not self.nos

    def origens_registradas(self):
        return {o.chave() for no in self.nos.values() for o in no.origens}

    def consultar(self, vetor, arquivos=None, quantos=4, max_arestas=14):
        if self.vazio:
            return [], []
        ids = list(self.nos)
        notas = self.vetores @ vetor

        centrais = []
        for i in np.argsort(-notas):
            if notas[i] < LIMIAR_PERGUNTA or len(centrais) >= quantos:
                break
            if arquivos is None or self.nos[ids[i]].arquivos() & arquivos:
                centrais.append(ids[i])
        if not centrais:
            return [], []

        centro = set(centrais)
        arestas = [a for a in self.arestas if a.de in centro or a.para in centro]
        if arquivos is not None:
            arestas = [a for a in arestas if not a.origens or a.arquivos() & arquivos]
        arestas.sort(key=lambda a: -((a.de in centro) + (a.para in centro)))
        return centrais, arestas[:max_arestas]

    def formatar(self, centrais, arestas, ids_por_arquivo=None):
        if not centrais:
            return ""
        ids_por_arquivo = ids_por_arquivo or {}
        linhas = ["CONTEXTO DO GRAFO (conceitos ligados à pergunta):"]
        for nid in centrais:
            no = self.nos[nid]
            descricao = f" — {no.descricao}" if no.descricao else ""
            linhas.append(f"• {no.nome} [{no.tipo or '?'}]{descricao} "
                          f"({_rotulos(no.origens, ids_por_arquivo)})")
        if arestas:
            linhas.append("Relações:")
            for aresta in arestas:
                de, para = self.nos[aresta.de].nome, self.nos[aresta.para].nome
                origens = _rotulos(aresta.origens, ids_por_arquivo)
                linhas.append(f"  {de} —{aresta.relacao}→ {para}" + (f" ({origens})" if origens else ""))
        return "\n".join(linhas)
