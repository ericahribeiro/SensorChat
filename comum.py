"""
Peças compartilhadas pelos tres scripts.

A ideia é a mesma do InsightFace: carrega um modelo uma vez,
passa lotes por ele, recebe vetores normalizados de volta,
e compara por produto escalar (= similaridade de cosseno,
já que os vetores estão normalizados).
"""
import os, json
import numpy as np

# ---------------------------------------------------------------------------
# MODELO DE EMBEDDING
#
# multilingual-e5-base entende português e inglês no mesmo espaço, que é o que
# você precisa: perguntar em português e achar trecho em inglês.
#
# ATENÇÃO ao detalhe do e5: ele exige um prefixo diferente para documento e
# para pergunta. Esquecer isso não dá erro — só piora a busca em silêncio.
# ---------------------------------------------------------------------------
MODELO = "intfloat/multilingual-e5-base"   # 768 dimensões, ~1.1 GB
PREFIXO_DOC = "passage: "
PREFIXO_PERGUNTA = "query: "

_modelo = None


def escolher_dispositivo():
    import torch
    if torch.backends.mps.is_available():
        return "mps"          # Apple Silicon
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def carregar_modelo():
    """Carrega uma vez e reaproveita (o import é lento, o modelo mais ainda)."""
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        dispositivo = escolher_dispositivo()
        print(f"carregando {MODELO} em {dispositivo}... (a primeira vez baixa ~1 GB)")
        _modelo = SentenceTransformer(MODELO, device=dispositivo)
    return _modelo


def vetorizar_documentos(textos, lote=32):
    m = carregar_modelo()
    return m.encode([PREFIXO_DOC + t for t in textos],
                    batch_size=lote,
                    normalize_embeddings=True,     # <- deixa o produto escalar virar cosseno
                    show_progress_bar=True,
                    convert_to_numpy=True).astype("float32")


def vetorizar_pergunta(texto):
    m = carregar_modelo()
    return m.encode([PREFIXO_PERGUNTA + texto],
                    normalize_embeddings=True,
                    convert_to_numpy=True).astype("float32")[0]


# ---------------------------------------------------------------------------
# BASES SEPARADAS
#
# Livros e artigos em bases diferentes, de propósito: vinte livros geram ~27 mil
# pedaços e trinta artigos geram ~1 mil. Na mesma base, os livros afogam os
# artigos e os números que você quer nunca sobem nos resultados.
# ---------------------------------------------------------------------------
def caminhos(base):
    return f"pdfs_{base}", f"base_{base}.npz", f"base_{base}.json"


def salvar_base(base, vetores, pedacos):
    _, npz, js = caminhos(base)
    np.savez_compressed(npz, vetores=vetores)
    with open(js, "w", encoding="utf-8") as f:
        json.dump(pedacos, f, ensure_ascii=False)


def carregar_base(base):
    _, npz, js = caminhos(base)
    if not os.path.exists(npz):
        raise SystemExit(f"Base '{base}' não existe. Rode:  python 1_indexar.py {base}")
    V = np.load(npz)["vetores"]
    with open(js, encoding="utf-8") as f:
        return V, json.load(f)


def buscar(pergunta, V, pedacos, quantos=6):
    """A 'busca vetorial' inteira: um produto escalar e um argsort."""
    q = vetorizar_pergunta(pergunta)
    similaridades = V @ q
    melhores = np.argsort(-similaridades)[:quantos]
    return [(float(similaridades[i]), pedacos[i]) for i in melhores]
