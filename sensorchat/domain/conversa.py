import json
from dataclasses import dataclass

SISTEMA = "system"
USUARIO = "user"
ASSISTENTE = "assistant"
FERRAMENTA = "tool"

AVISO_INTERROMPIDA = "\n\n[fala interrompida: estourou o limite de tokens]"


@dataclass(frozen=True)
class ChamadaFerramenta:
    id: str
    nome: str
    argumentos: str

    def argumentos_dict(self):
        try:
            dados = json.loads(self.argumentos or "{}")
        except json.JSONDecodeError:
            return {}
        return dados if isinstance(dados, dict) else {}


@dataclass(frozen=True)
class Mensagem:
    papel: str
    conteudo: str
    chamadas: tuple = ()
    id_chamada: str | None = None

    @classmethod
    def sistema(cls, conteudo):
        return cls(SISTEMA, conteudo)

    @classmethod
    def usuario(cls, conteudo):
        return cls(USUARIO, conteudo)

    @classmethod
    def assistente(cls, conteudo, chamadas=()):
        return cls(ASSISTENTE, conteudo, tuple(chamadas))

    @classmethod
    def resultado(cls, id_chamada, conteudo):
        return cls(FERRAMENTA, conteudo, id_chamada=id_chamada)


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    parametros: dict


@dataclass(frozen=True)
class RespostaModelo:
    texto: str
    chamadas: tuple = ()
    interrompida: bool = False

    def texto_completo(self):
        texto = self.texto.strip()
        if self.interrompida or not texto:
            texto += AVISO_INTERROMPIDA
        return texto


@dataclass(frozen=True)
class Consulta:
    ferramenta: str
    documentos: tuple
    arquivos: tuple
    pergunta: str
    conceitos: tuple | None = None

    @classmethod
    def de_dict(cls, dados):
        conceitos = dados.get("conceitos")
        return cls(dados["ferramenta"], tuple(dados.get("documentos", [])),
                   tuple(dados.get("arquivos", [])), dados.get("pergunta", ""),
                   tuple(conceitos) if conceitos is not None else None)

    def como_dict(self):
        dados = {"ferramenta": self.ferramenta, "documentos": list(self.documentos),
                 "arquivos": list(self.arquivos), "pergunta": self.pergunta}
        if self.conceitos is not None:
            dados["conceitos"] = list(self.conceitos)
        return dados
