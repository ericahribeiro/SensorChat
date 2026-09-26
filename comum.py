
import os, json
import numpy as np

MODELO = "intfloat/multilingual-e5-base"
PREFIXO_DOC = "passage: "
PREFIXO_PERGUNTA = "query: "

_modelo = None


def escolher_dispositivo():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def carregar_modelo():
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
                    normalize_embeddings=True,
                    show_progress_bar=True,
                    convert_to_numpy=True).astype("float32")


def vetorizar_pergunta(texto):
    m = carregar_modelo()
    return m.encode([PREFIXO_PERGUNTA + texto],
                    normalize_embeddings=True,
                    convert_to_numpy=True).astype("float32")[0]


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
    q = vetorizar_pergunta(pergunta)
    similaridades = V @ q
    melhores = np.argsort(-similaridades)[:quantos]
    return [(float(similaridades[i]), pedacos[i]) for i in melhores]
