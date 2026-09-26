
import os, sys, json, pathlib
import numpy as np
from openai import OpenAI

from comum import carregar_base
from busca_multi import BASES, CATALOGO

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
MODELO = "mimo-v2.5"
AMOSTRA = 40
MAX_CHARS_PEDACO = 900

INSTRUCOES = """Você recebe trechos amostrados de um documento (artigo científico ou livro
sobre sensores inerciais, biomecânica ou treino). Os trechos vêm com o número da
página. Devolva JSON puro, sem cerca de código, no formato:

{"descricao": "...", "resumo": "..."}

descricao — em português, 3 ou 4 frases. Comece pelo tipo (revisão sistemática,
livro-texto, artigo de método, estudo de validação...). Diga QUE PERGUNTAS este
documento responde e QUE TIPO DE DADO tem (números de validade por dispositivo,
equações de fusão, tabelas comparativas, protocolo experimental, recomendações
práticas). Diga o que só ele tem, não o tema genérico: "fala de IMU" não ajuda,
todos falam de IMU. Termos técnicos em inglês entre parênteses na primeira vez.

resumo — em português, até 600 palavras. Os achados principais com os números
que aparecem nos trechos e a página entre parênteses: "(p. 7)". Não invente
número que não esteja nos trechos. Se os trechos forem só uma amostra e faltar
o miolo, diga o que a amostra cobre."""


def amostrar(pedacos):
    idx = np.linspace(0, len(pedacos) - 1, min(len(pedacos), AMOSTRA)).astype(int)
    return [pedacos[i] for i in sorted(set(idx))]


def descrever(cliente, arquivo, pedacos):
    corpo = "\n\n---\n\n".join(
        f"(página {p['pagina']})\n{p['texto'][:MAX_CHARS_PEDACO]}" for p in amostrar(pedacos))
    r = cliente.chat.completions.create(
        model=MODELO,
        messages=[{"role": "system", "content": INSTRUCOES},
                  {"role": "user", "content": f"ARQUIVO: {arquivo}\n"
                                              f"TRECHOS ({len(pedacos)} no total, "
                                              f"{min(len(pedacos), AMOSTRA)} amostrados):\n\n{corpo}"}],
        max_completion_tokens=2000,
        extra_body={"thinking": {"type": "disabled"}},
    )
    bruto = (r.choices[0].message.content or "").strip()
    bruto = bruto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(bruto)


def main():
    if not API_KEY:
        raise SystemExit("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")
    tudo = "--tudo" in sys.argv
    filtro = None
    if "--so" in sys.argv:
        filtro = sys.argv[sys.argv.index("--so") + 1].lower()

    existentes = {}
    if CATALOGO.exists():
        existentes = {d["arquivo"]: d for d in json.loads(CATALOGO.read_text(encoding="utf-8"))}

    cliente = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    feitos, falhas = 0, []

    for base in BASES:
        try:
            _, pedacos = carregar_base(base)
        except SystemExit as e:
            print(f"  (aviso: {e})")
            continue
        por_arquivo = {}
        for p in pedacos:
            por_arquivo.setdefault(p["arquivo"], []).append(p)

        for arquivo, ps in sorted(por_arquivo.items()):
            if filtro and filtro not in arquivo.lower():
                continue
            if not tudo and not filtro and existentes.get(arquivo, {}).get("descricao"):
                continue
            print(f"  {arquivo[:64]} ({len(ps)} trechos)... ", end="", flush=True)
            try:
                d = descrever(cliente, arquivo, ps)
                existentes[arquivo] = {"arquivo": arquivo, "base": base,
                                       "descricao": d["descricao"].strip(),
                                       "resumo": d["resumo"].strip()}
                feitos += 1
                print("ok")
                CATALOGO.write_text(json.dumps(list(existentes.values()),
                                               ensure_ascii=False, indent=1),
                                    encoding="utf-8")
            except Exception as e:
                falhas.append((arquivo, str(e)[:120]))
                print(f"FALHOU: {e}")

    print(f"\n{feitos} descritos, {len(existentes)} no catálogo -> {CATALOGO}")
    for arq, e in falhas:
        print(f"  falhou {arq[:50]}: {e}")


if __name__ == "__main__":
    main()
