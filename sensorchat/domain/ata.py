from dataclasses import dataclass, field

from .conversa import Consulta

HUMANO = "humano"
AGENTE = "agente"


@dataclass(frozen=True)
class Linha:
    n: int
    autor: str
    papel: str
    texto: str
    quando: str
    consultas: tuple = ()

    @classmethod
    def de_dict(cls, dados):
        return cls(dados["n"], dados["autor"], dados["papel"], dados["texto"], dados["quando"],
                   tuple(Consulta.de_dict(c) for c in dados.get("buscas", [])))

    def como_dict(self):
        dados = {"n": self.n, "autor": self.autor, "papel": self.papel,
                 "texto": self.texto, "quando": self.quando}
        if self.consultas:
            dados["buscas"] = [c.como_dict() for c in self.consultas]
        return dados


def _lista(valor):
    return [str(v) for v in valor] if isinstance(valor, list) else []


@dataclass(frozen=True)
class Plano:
    decisoes: list = field(default_factory=list)
    abertas: list = field(default_factory=list)
    riscos: list = field(default_factory=list)

    @classmethod
    def de_dict(cls, dados):
        dados = dados if isinstance(dados, dict) else {}
        return cls(_lista(dados.get("decisoes")), _lista(dados.get("abertas")), _lista(dados.get("riscos")))

    def como_dict(self):
        return {"decisoes": list(self.decisoes), "abertas": list(self.abertas), "riscos": list(self.riscos)}


class Ata:
    def __init__(self, linhas=None, plano=None):
        self.linhas = list(linhas or [])
        self.plano = plano or Plano()

    @classmethod
    def de_dict(cls, dados):
        return cls([Linha.de_dict(l) for l in dados.get("linhas", [])],
                   Plano.de_dict(dados.get("plano")))

    def como_dict(self):
        return {"linhas": [l.como_dict() for l in self.linhas], "plano": self.plano.como_dict()}

    def acrescentar(self, autor, papel, texto, quando, consultas=()):
        linha = Linha(len(self.linhas), autor, papel, texto.strip(), quando, tuple(consultas))
        self.linhas.append(linha)
        return linha

    def definir_plano(self, plano):
        self.plano = plano

    def em_texto(self, limite=60):
        return "\n\n".join(f"{l.autor}: {l.texto}" for l in self.linhas[-limite:])

    def ultima_fala_humana(self):
        return next((l.texto for l in reversed(self.linhas) if l.papel == HUMANO), "")
