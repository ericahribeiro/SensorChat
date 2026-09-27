from datetime import datetime
from typing import Callable, Protocol, Sequence

import numpy as np

from ..domain.ata import Ata
from ..domain.conversa import Ferramenta, Mensagem, RespostaModelo
from ..domain.documentos import BaseVetorial, Descricao, Pedaco
from ..domain.grafo import GrafoConceitos
from ..domain.limpeza import PaginaBruta


class Vetorizador(Protocol):
    def vetorizar_documentos(self, textos: Sequence[str], lote: int = 32) -> np.ndarray: ...

    def vetorizar_pergunta(self, texto: str) -> np.ndarray: ...


class ModeloLinguagem(Protocol):
    def completar(self, modelo: str, mensagens: Sequence[Mensagem], max_tokens: int,
                  ferramentas: Sequence[Ferramenta] = (), sem_raciocinio: bool = False) -> RespostaModelo: ...


class RepositorioBases(Protocol):
    def nomes(self) -> tuple[str, ...]: ...

    def carregar(self, nome: str) -> BaseVetorial: ...

    def salvar(self, nome: str, vetores: np.ndarray, pedacos: Sequence[Pedaco]) -> None: ...


class RepositorioCatalogo(Protocol):
    def descricoes(self) -> dict[str, Descricao]: ...

    def salvar(self, descricoes: Sequence[Descricao]) -> None: ...


class RepositorioGrafo(Protocol):
    def carregar(self) -> GrafoConceitos | None: ...

    def salvar(self, grafo: GrafoConceitos) -> None: ...


class RepositorioExtracoes(Protocol):
    def carregar(self) -> dict: ...

    def salvar(self, extracoes: dict) -> None: ...


class RepositorioAta(Protocol):
    def ler(self) -> Ata: ...

    def alterar(self, alteracao: Callable[[Ata], object]) -> object: ...


class FonteDocumentos(Protocol):
    def local(self, base: str) -> str: ...

    def listar(self, base: str) -> list[str]: ...

    def ler(self, caminho: str) -> list[PaginaBruta]: ...


class PublicadorAta(Protocol):
    def publicar(self, ata: Ata, momento: datetime) -> str: ...


Avisar = Callable[[str], None]
