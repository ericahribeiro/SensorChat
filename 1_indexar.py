import sys, os, re, glob
import pymupdf
from comum import caminhos, vetorizar_documentos, salvar_base

ALVO_PEDACO = 900
SOBREPOSICAO = 150


def ler_pdf(caminho):
    doc = pymupdf.open(caminho)
    paginas = []
    for i, pagina in enumerate(doc):
        texto = pagina.get_text(sort=True)          # sort=True respeita duas colunas
        paginas.append((i + 1, re.sub(r"\n{3,}", "\n\n", texto)))
    return paginas


def picar(paginas, arquivo):
    pedacos = []
    for numero, texto in paginas:
        paragrafos = [p.strip() for p in texto.split("\n\n") if len(p.strip()) > 40]
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
    return pedacos


def main():
    if len(sys.argv) != 2:
        print("Uso: python 1_indexar.py <nome_da_base>    (ex: artigos, livros)")
        sys.exit(1)
    base = sys.argv[1]
    pasta, _, _ = caminhos(base)

    os.makedirs(pasta, exist_ok=True)
    arquivos = sorted(glob.glob(os.path.join(pasta, "*.pdf")))
    if not arquivos:
        print(f"Nenhum PDF em ./{pasta}/ — coloque os arquivos lá e rode de novo.")
        return

    todos = []
    for caminho in arquivos:
        nome = os.path.basename(caminho)
        try:
            paginas = ler_pdf(caminho)
        except Exception as e:
            print(f"  FALHOU {nome}: {e}")
            continue
        chars = sum(len(t) for _, t in paginas)
        if chars < 500:
            print(f"  AVISO {nome}: quase nenhum texto — provável PDF escaneado, precisa de OCR")
            continue
        pedacos = picar(paginas, nome)
        print(f"  {nome}: {len(paginas)} pág, {len(pedacos)} pedaços")
        todos.extend(pedacos)

    if not todos:
        print("Nada para indexar.")
        return

    print(f"\nVetorizando {len(todos)} pedaços localmente...")
    V = vetorizar_documentos([p["texto"] for p in todos])
    salvar_base(base, V, todos)
    print(f"\nPronto: base_{base}.npz ({V.nbytes/1e6:.0f} MB) com {len(todos)} pedaços "
          f"de {len(arquivos)} arquivos.")


if __name__ == "__main__":
    main()
