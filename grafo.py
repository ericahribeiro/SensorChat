
import json, pathlib
import numpy as np
from comum import vetorizar_pergunta

GRAFO_JSON = pathlib.Path("grafo.json")
GRAFO_NPZ = pathlib.Path("grafo.npz")
LIMIAR_PERGUNTA = 0.80

_cache = None


def vazio():
    return {"nos": {}, "arestas": []}


def carregar():

    global _cache
    if _cache is None:
        if not GRAFO_JSON.exists() or not GRAFO_NPZ.exists():
            _cache = (None, None)
        else:
            g = json.loads(GRAFO_JSON.read_text(encoding="utf-8"))
            V = np.load(GRAFO_NPZ)["vetores"]
            _cache = (g, V)
    return _cache


def invalidar():
    global _cache
    _cache = None


def _arquivos_do_no(no):
    return {o["arquivo"] for o in no.get("origens", [])}


def consultar(pergunta, arquivos=None, quantos=4, max_arestas=14):

    g, V = carregar()
    if g is None or not g["nos"]:
        return [], []
    ids = list(g["nos"])
    q = vetorizar_pergunta(pergunta)
    notas = V @ q
    permitidos = None if not arquivos else set(arquivos)

    centrais = []
    for i in np.argsort(-notas):
        if notas[i] < LIMIAR_PERGUNTA or len(centrais) >= quantos:
            break
        no = g["nos"][ids[i]]
        if permitidos is None or _arquivos_do_no(no) & permitidos:
            centrais.append(ids[i])
    if not centrais:
        return [], []

    centro = set(centrais)
    arestas = [a for a in g["arestas"] if a["de"] in centro or a["para"] in centro]
    if permitidos is not None:
        arestas = [a for a in arestas
                   if not a.get("origens") or {o["arquivo"] for o in a["origens"]} & permitidos]
    arestas.sort(key=lambda a: -((a["de"] in centro) + (a["para"] in centro)))
    return centrais, arestas[:max_arestas]


def _origem_curta(origens, ids_por_arquivo):
    vistos, partes = set(), []
    for o in origens:
        rot = ids_por_arquivo.get(o["arquivo"], o["arquivo"][:20])
        if o.get("pagina"):
            rot += f" p.{o['pagina']}"
        if rot not in vistos:
            vistos.add(rot)
            partes.append(rot)
    return ", ".join(partes[:3])


def formatar(centrais, arestas, ids_por_arquivo=None):
    g, _ = carregar()
    if not centrais:
        return ""
    ids_por_arquivo = ids_por_arquivo or {}
    linhas = ["CONTEXTO DO GRAFO (conceitos ligados à pergunta):"]
    for cid in centrais:
        no = g["nos"][cid]
        desc = f" — {no['descricao']}" if no.get("descricao") else ""
        linhas.append(f"• {no['nome']} [{no.get('tipo', '?')}]{desc} "
                      f"({_origem_curta(no.get('origens', []), ids_por_arquivo)})")
    if arestas:
        linhas.append("Relações:")
        for a in arestas:
            de, para = g["nos"][a["de"]]["nome"], g["nos"][a["para"]]["nome"]
            org = _origem_curta(a.get("origens", []), ids_por_arquivo)
            linhas.append(f"  {de} —{a['relacao']}→ {para}" + (f" ({org})" if org else ""))
    return "\n".join(linhas)
