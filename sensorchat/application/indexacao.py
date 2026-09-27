import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..domain.fatiamento import picar
from ..domain.limpeza import cortar_referencias, limpar_paginas
from ..domain.prosa import classificar

MIN_CARACTERES = 500
LIMITE_DESCARTE = 0.5
LIMITE_DOMINANCIA = 0.60
EXEMPLOS_POR_MOTIVO = 2


@dataclass
class ResultadoDoArquivo:
    nome: str
    paginas: int
    cabecalhos: int
    pagina_referencias: int | None
    brutos: int
    mantidos: list
    motivos: Counter = field(default_factory=Counter)

    @property
    def descartado(self):
        return 1 - len(self.mantidos) / max(self.brutos, 1)


class IndexarBase:
    def __init__(self, fonte, bases, vetorizador, avisar=print):
        self._fonte = fonte
        self._bases = bases
        self._vetorizador = vetorizador
        self._avisar = avisar

    def executar(self, nome, mostrar=False):
        arquivos = self._fonte.listar(nome)
        if not arquivos:
            self._avisar(f"Nenhum PDF em ./{self._fonte.local(nome)}/ — coloque os arquivos lá e rode de novo.")
            return 0

        todos, exemplos = [], defaultdict(list)
        for caminho in arquivos:
            resultado = self._processar(caminho, exemplos)
            if resultado:
                self._relatar(resultado)
                todos.extend(resultado.mantidos)

        if not todos:
            self._avisar("Nada para indexar.")
            return 0
        if mostrar and exemplos:
            self._mostrar_exemplos(exemplos)
        self._alertar_dominancia(todos)

        self._avisar(f"\nVetorizando {len(todos)} pedaços localmente...")
        vetores = self._vetorizador.vetorizar_documentos([p.texto for p in todos])
        self._bases.salvar(nome, vetores, todos)
        self._avisar(f"\nPronto: base '{nome}' ({vetores.nbytes / 1e6:.0f} MB) com {len(todos)} pedaços "
                     f"de {len(arquivos)} arquivos.")
        return len(todos)

    def _processar(self, caminho, exemplos):
        nome = os.path.basename(caminho)
        try:
            brutas = self._fonte.ler(caminho)
        except Exception as erro:
            self._avisar(f"  FALHOU {nome}: {erro}")
            return None

        paginas, lixo = limpar_paginas(brutas)
        if sum(len(p.texto) for p in paginas) < MIN_CARACTERES:
            self._avisar(f"  AVISO {nome}: quase nenhum texto — provável PDF escaneado, precisa de OCR")
            return None

        paginas, pagina_referencias = cortar_referencias(paginas)
        brutos = picar(paginas, nome)
        resultado = ResultadoDoArquivo(nome, len(paginas), len(lixo), pagina_referencias, len(brutos), [])
        for pedaco in brutos:
            motivo = classificar(pedaco.texto)
            if motivo is None:
                resultado.mantidos.append(pedaco)
                continue
            resultado.motivos[motivo] += 1
            if len(exemplos[motivo]) < EXEMPLOS_POR_MOTIVO:
                exemplos[motivo].append((nome, pedaco.pagina, pedaco.texto[:220]))
        return resultado

    def _relatar(self, resultado):
        detalhe = f"{resultado.paginas} pág"
        if resultado.cabecalhos:
            detalhe += f" | {resultado.cabecalhos} cabeçalho/rodapé"
        if resultado.pagina_referencias:
            detalhe += f" | refs na pág {resultado.pagina_referencias}"
        self._avisar(f"  {resultado.nome[:60]}: {detalhe} | {resultado.brutos} -> "
                     f"{len(resultado.mantidos)} pedaços")
        if resultado.motivos:
            self._avisar("      descartados: " + ", ".join(
                f"{c} {m}" for m, c in resultado.motivos.most_common()))
        if resultado.descartado > LIMITE_DESCARTE:
            self._avisar(f"      ATENÇÃO: {resultado.descartado:.0%} descartado. Confira com --mostrar.")

    def _mostrar_exemplos(self, exemplos):
        self._avisar("\n" + "=" * 70 + "\nEXEMPLOS DO QUE FOI DESCARTADO\n" + "=" * 70)
        for motivo, itens in exemplos.items():
            self._avisar(f"\n--- {motivo} ---")
            for arquivo, pagina, texto in itens:
                self._avisar(f"  [{arquivo[:40]}, pág {pagina}]\n  {texto!r}\n")

    def _alertar_dominancia(self, todos):
        por_arquivo = Counter(p.arquivo for p in todos)
        maior, quantidade = por_arquivo.most_common(1)[0]
        if quantidade / len(todos) > LIMITE_DOMINANCIA and len(por_arquivo) > 1:
            self._avisar(f"\n  ATENÇÃO: '{maior[:50]}' é {quantidade / len(todos):.0%} da base.")
            self._avisar("  Um documento dominando assim afoga os outros na busca.")
