from dataclasses import dataclass

import numpy as np

TODOS = "todos"


def e_todos(nome):
    return nome.strip().lower() == TODOS


@dataclass(frozen=True)
class Pedaco:
    arquivo: str
    pagina: int | None
    texto: str

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["arquivo"], dados.get("pagina"), dados["texto"])

    def como_dict(self):
        return {"arquivo": self.arquivo, "pagina": self.pagina, "texto": self.texto}


@dataclass(frozen=True)
class Trecho:
    nota: float
    pedaco: Pedaco
    base: str

    def formatar(self):
        return f"[{self.base} · {self.pedaco.arquivo}, página {self.pedaco.pagina}]\n{self.pedaco.texto}"


def formatar_trechos(trechos):
    return "\n\n---\n\n".join(t.formatar() for t in trechos)


class BaseVetorial:
    def __init__(self, nome, vetores, pedacos):
        self.nome = nome
        self.vetores = vetores
        self.pedacos = list(pedacos)
        self.arquivos = np.array([p.arquivo for p in self.pedacos], dtype=str)

    def melhores(self, vetor, total):
        notas = self.vetores @ vetor
        return self._melhores_entre(notas, np.arange(len(self.pedacos)), total)

    def melhores_por_selecao(self, vetor, arquivos, total):
        notas = self.vetores @ vetor
        if arquivos is None:
            mascara = np.ones(len(self.pedacos), bool)
        else:
            mascara = np.isin(self.arquivos, sorted(arquivos))
        return (self._melhores_entre(notas, np.flatnonzero(mascara), total),
                self._melhores_entre(notas, np.flatnonzero(~mascara), total))

    def contagem_por_arquivo(self):
        nomes, contagem = np.unique(self.arquivos, return_counts=True)
        return [(str(arquivo), int(n)) for arquivo, n in zip(nomes, contagem)]

    def por_arquivo(self):
        grupos = {}
        for pedaco in self.pedacos:
            grupos.setdefault(pedaco.arquivo, []).append(pedaco)
        return dict(sorted(grupos.items()))

    def _melhores_entre(self, notas, indices, total):
        if not len(indices):
            return []
        topo = indices[np.argsort(-notas[indices])[:total]]
        return [Trecho(float(notas[i]), self.pedacos[i], self.nome) for i in topo]


@dataclass(frozen=True)
class Descricao:
    arquivo: str
    base: str
    descricao: str
    resumo: str

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["arquivo"], dados.get("base", ""),
                   dados.get("descricao", ""), dados.get("resumo", ""))

    def como_dict(self):
        return {"arquivo": self.arquivo, "base": self.base,
                "descricao": self.descricao, "resumo": self.resumo}


@dataclass(frozen=True)
class DocumentoCatalogado:
    id: str
    base: str
    arquivo: str
    pedacos: int
    descricao: str
    resumo: str

    def formatar(self):
        cabeca = f"[{self.id}] {self.base} · {self.arquivo} ({self.pedacos} trechos)"
        corpo = self.descricao or "(sem descrição — rode python -m sensorchat descrever)"
        return f"{cabeca}\n    {corpo}"


@dataclass(frozen=True)
class Selecao:
    arquivos: frozenset | None
    nao_encontrados: tuple


class Catalogo:
    def __init__(self, itens):
        self.itens = tuple(itens)

    @classmethod
    def montar(cls, bases, descricoes):
        itens = []
        for base in bases:
            for i, (arquivo, pedacos) in enumerate(base.contagem_por_arquivo(), start=1):
                descricao = descricoes.get(arquivo)
                itens.append(DocumentoCatalogado(
                    id=f"{base.nome[0].upper()}{i}",
                    base=base.nome,
                    arquivo=arquivo,
                    pedacos=pedacos,
                    descricao=descricao.descricao if descricao else "",
                    resumo=descricao.resumo if descricao else "",
                ))
        return cls(itens)

    def __iter__(self):
        return iter(self.itens)

    def __len__(self):
        return len(self.itens)

    def resolver(self, nome):
        chave = nome.strip().lower()
        for item in self.itens:
            if chave in (item.id.lower(), item.arquivo.lower()):
                return item
        parecidos = [item for item in self.itens if chave in item.arquivo.lower()]
        return parecidos[0] if len(parecidos) == 1 else None

    def arquivo_de(self, nome):
        item = self.resolver(nome)
        return item.arquivo if item else nome

    def selecionar(self, documentos):
        arquivos, nao_encontrados = set(), []
        for nome in documentos or []:
            if e_todos(nome):
                return Selecao(None, tuple(nao_encontrados))
            item = self.resolver(nome)
            if item:
                arquivos.add(item.arquivo)
            else:
                nao_encontrados.append(nome)
        return Selecao(frozenset(arquivos) or None, tuple(nao_encontrados))

    def ids_por_arquivo(self):
        return {item.arquivo: item.id for item in self.itens}

    def formatar(self):
        return "\n".join(item.formatar() for item in self.itens)
