
import sys, os, glob
from collections import Counter, defaultdict

from comum import caminhos, vetorizar_documentos, salvar_base
from limpeza import ler_paginas, cortar_referencias
from prosa import classificar

ALVO_PEDACO = 900
SOBREPOSICAO = 150
MIN_PARAGRAFO = 40
MIN_PEDACO = 250


def picar(paginas, arquivo):
    pedacos = []
    for numero, texto in paginas:
        paragrafos = [p.strip() for p in texto.split("\n\n")
                      if len(p.strip()) > MIN_PARAGRAFO]
        buffer = ""
        for p in paragrafos:
            if len(buffer) + len(p) < ALVO_PEDACO:
                buffer += ("\n\n" if buffer else "") + p
            else:
                if buffer:
                    pedacos.append({"arquivo": arquivo, "pagina": numero, "texto": buffer})
                buffer = (buffer[-SOBREPOSICAO:] + "\n\n" + p) if buffer else p
        if buffer:
            pedacos.append({"arquivo": arquivo, "pagina": numero, "texto": buffer})
    return [p for p in pedacos if len(p["texto"]) >= MIN_PEDACO]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mostrar = "--mostrar" in sys.argv
    if len(args) != 1:
        print("Uso: python 1_indexar.py <base> [--mostrar]")
        sys.exit(1)
    base = args[0]
    pasta, _, _ = caminhos(base)

    os.makedirs(pasta, exist_ok=True)
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
    if not arquivos:
        print(f"Nenhum PDF em ./{pasta}/ — coloque os arquivos lá e rode de novo.")
        return

    todos = []
    exemplos = defaultdict(list)

    for caminho in arquivos:
        nome = os.path.basename(caminho)
        try:
            paginas, lixo = ler_paginas(caminho)
        except Exception as e:
            print(f"  FALHOU {nome}: {e}")
            continue

        if sum(len(t) for _, t in paginas) < 500:
            print(f"  AVISO {nome}: quase nenhum texto — provável PDF escaneado, precisa de OCR")
            continue

        paginas, pag_ref = cortar_referencias(paginas)
        brutos = picar(paginas, nome)

        mantidos, motivos = [], Counter()
        for p in brutos:
            motivo = classificar(p["texto"])
            if motivo is None:
                mantidos.append(p)
            else:
                motivos[motivo] += 1
                if len(exemplos[motivo]) < 2:
                    exemplos[motivo].append((nome, p["pagina"], p["texto"][:220]))

        detalhe = f"{len(paginas)} pág"
        if lixo:
            detalhe += f" | {len(lixo)} cabeçalho/rodapé"
        if pag_ref:
            detalhe += f" | refs na pág {pag_ref}"
        print(f"  {nome[:60]}: {detalhe} | {len(brutos)} -> {len(mantidos)} pedaços")
        if motivos:
            print("      descartados: " +
                  ", ".join(f"{c} {m}" for m, c in motivos.most_common()))

        descartado = 1 - len(mantidos) / max(len(brutos), 1)
        if descartado > 0.5:
            print(f"      ATENÇÃO: {descartado:.0%} descartado. Confira com --mostrar.")

        todos.extend(mantidos)

    if not todos:
        print("Nada para indexar.")
        return

    if mostrar and exemplos:
        print("\n" + "=" * 70 + "\nEXEMPLOS DO QUE FOI DESCARTADO\n" + "=" * 70)
        for motivo, itens in exemplos.items():
            print(f"\n--- {motivo} ---")
            for arq, pag, txt in itens:
                print(f"  [{arq[:40]}, pág {pag}]\n  {txt!r}\n")

    por_arquivo = Counter(p["arquivo"] for p in todos)
    maior, qtd = por_arquivo.most_common(1)[0]
    if qtd / len(todos) > 0.60 and len(por_arquivo) > 1:
        print(f"\n  ATENÇÃO: '{maior[:50]}' é {qtd/len(todos):.0%} da base.")
        print("  Um documento dominando assim afoga os outros na busca.")

    print(f"\nVetorizando {len(todos)} pedaços localmente...")
    V = vetorizar_documentos([p["texto"] for p in todos])
    salvar_base(base, V, todos)
    print(f"\nPronto: base_{base}.npz ({V.nbytes/1e6:.0f} MB) com {len(todos)} pedaços "
          f"de {len(arquivos)} arquivos.")


if __name__ == "__main__":
    main()