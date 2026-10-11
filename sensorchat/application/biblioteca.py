from dataclasses import dataclass
from pathlib import PurePosixPath

from ..domain.documentos import DocumentoCatalogado
from ..domain.erros import ArquivoInvalido, ArquivoRepetido, DocumentoDesconhecido
from ..domain.leitura import montar_blocos, titulo_de

ASSINATURA_PDF = b"%PDF-"
TAMANHO_MAXIMO = 150 * 1024 * 1024


@dataclass(frozen=True)
class DocumentoNaEstante:
    item: DocumentoCatalogado
    titulo: str
    tem_pdf: bool

    def como_dict(self):
        return {"id": self.item.id, "base": self.item.base, "arquivo": self.item.arquivo,
                "titulo": self.titulo, "trechos": self.item.pedacos, "descricao": self.item.descricao,
                "resumo": self.item.resumo, "tem_pdf": self.tem_pdf}


class Biblioteca:
    def __init__(self, busca, fonte):
        self._busca = busca
        self._fonte = fonte

    def bases(self):
        return self._busca.nomes()

    def documentos(self):
        return [self._na_estante(item) for item in self._busca.catalogo()]

    def pendentes(self):
        indexados = {item.arquivo for item in self._busca.catalogo()}
        return {base: [nome for nome in self._nomes_na_pasta(base) if nome not in indexados]
                for base in self.bases()}

    def abrir(self, referencia):
        item = self._item(referencia)
        pedacos = self._busca.base(item.base).por_arquivo()[item.arquivo]
        return self._na_estante(item), montar_blocos(pedacos)

    def pdf(self, referencia):
        item = self._item(referencia)
        return self._fonte.caminho(item.base, item.arquivo)

    def guardar(self, base, nome, dados):
        if base not in self.bases():
            raise ArquivoInvalido(f"base desconhecida: '{base}' (use {' ou '.join(self.bases())})")
        nome = PurePosixPath(str(nome).replace("\\", "/")).name.strip()
        if not nome or nome.startswith(".") or not nome.lower().endswith(".pdf"):
            raise ArquivoInvalido("o arquivo precisa ser um .pdf")
        if not dados.startswith(ASSINATURA_PDF):
            raise ArquivoInvalido(f"'{nome}' não é um PDF")
        if len(dados) > TAMANHO_MAXIMO:
            raise ArquivoInvalido(f"'{nome}' passa de {TAMANHO_MAXIMO // 2**20} MB")
        if any(nome in self._nomes_na_pasta(b) for b in self.bases()) \
                or any(nome == item.arquivo for item in self._busca.catalogo()):
            raise ArquivoRepetido(nome)
        self._fonte.guardar(base, nome, dados)
        return nome

    def _item(self, referencia):
        item = self._busca.catalogo().resolver(referencia)
        if item is None:
            raise DocumentoDesconhecido(referencia)
        return item

    def _na_estante(self, item):
        return DocumentoNaEstante(item, titulo_de(item.arquivo),
                                  self._fonte.caminho(item.base, item.arquivo) is not None)

    def _nomes_na_pasta(self, base):
        return [PurePosixPath(caminho.replace("\\", "/")).name for caminho in self._fonte.listar(base)]
