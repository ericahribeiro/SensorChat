
import json, pathlib
import numpy as np
from comum import carregar_base, vetorizar_pergunta

COTAS_PADRAO = {"artigos": 3, "livros": 3}
BASES = ("artigos", "livros")
CATALOGO = pathlib.Path("catalogo.json")

_cache = {}


def _base(nome):
    if nome not in _cache:
        V, pedacos = carregar_base(nome)
        arquivos = np.array([p["arquivo"] for p in pedacos])
        _cache[nome] = (V, pedacos, arquivos)
    return _cache[nome]


def buscar_varias(pergunta, cotas=None, total=6, silencioso=False):

    cotas = cotas or COTAS_PADRAO
    q = vetorizar_pergunta(pergunta)

    candidatos = {}
    for nome in cotas:
        try:
            V, pedacos, _ = _base(nome)
        except SystemExit as e:
            if not silencioso:
                print(f"  (aviso: {e})")
            continue
        notas = V @ q
        ordem = np.argsort(-notas)[:total]
        candidatos[nome] = [(float(notas[i]), pedacos[i]) for i in ordem]

    if not candidatos:
        raise SystemExit("Nenhuma base disponível. Rode 1_indexar.py primeiro.")

    escolhidos, usados = [], {b: 0 for b in candidatos}

    for nome, lista in candidatos.items():
        for nota, p in lista[:cotas.get(nome, 0)]:
            escolhidos.append((nota, p, nome))
            usados[nome] += 1

    sobra = [(n, p, b) for b, lista in candidatos.items()
             for n, p in lista[usados[b]:]]
    sobra.sort(key=lambda t: -t[0])
    escolhidos.extend(sobra[:max(0, total - len(escolhidos))])

    escolhidos.sort(key=lambda t: -t[0])
    return escolhidos[:total]


def _descricoes():
    if CATALOGO.exists():
        return {d["arquivo"]: d for d in json.loads(CATALOGO.read_text(encoding="utf-8"))}
    return {}


def catalogo(bases=BASES):
    desc = _descricoes()
    itens = []
    for nome in bases:
        try:
            _, _, arquivos = _base(nome)
        except SystemExit:
            continue
        nomes, contagem = np.unique(arquivos, return_counts=True)
        for i, (arq, n) in enumerate(zip(nomes, contagem), start=1):
            d = desc.get(arq, {})
            itens.append({"id": f"{nome[0].upper()}{i}", "base": nome, "arquivo": arq,
                          "pedacos": int(n),
                          "descricao": d.get("descricao", ""),
                          "resumo": d.get("resumo", "")})
    return itens


def resolver(nome, itens=None):
    itens = itens or catalogo()
    chave = nome.strip().lower()
    for it in itens:
        if chave in (it["id"].lower(), it["arquivo"].lower()):
            return it
    parecidos = [it for it in itens if chave in it["arquivo"].lower()]
    return parecidos[0] if len(parecidos) == 1 else None


def formatar_catalogo(itens=None):
    itens = itens or catalogo()
    linhas = []
    for it in itens:
        cabeca = f"[{it['id']}] {it['base']} · {it['arquivo']} ({it['pedacos']} trechos)"
        corpo = it["descricao"] or "(sem descrição — rode descrever.py)"
        linhas.append(f"{cabeca}\n    {corpo}")
    return "\n".join(linhas)


def buscar_em(pergunta, documentos=None, total=6, fora=2):
    itens = catalogo()
    escolhidos, nao_encontrados = set(), []
    for nome in documentos or []:
        if nome.strip().lower() == "todos":
            escolhidos = None
            break
        it = resolver(nome, itens)
        if it:
            escolhidos.add(it["arquivo"])
        else:
            nao_encontrados.append(nome)
    if not escolhidos:
        escolhidos = None

    q = vetorizar_pergunta(pergunta)
    dentro, restante = [], []
    for nome in BASES:
        try:
            V, pedacos, arquivos = _base(nome)
        except SystemExit:
            continue
        notas = V @ q
        mascara = np.ones(len(pedacos), bool) if escolhidos is None \
            else np.isin(arquivos, list(escolhidos))
        for grupo, idx in ((dentro, np.flatnonzero(mascara)),
                           (restante, np.flatnonzero(~mascara))):
            if len(idx):
                top = idx[np.argsort(-notas[idx])[:total]]
                grupo.extend((float(notas[i]), pedacos[i], nome) for i in top)

    if not dentro and not restante:
        raise SystemExit("Nenhuma base disponível. Rode 1_indexar.py primeiro.")

    dentro.sort(key=lambda t: -t[0])
    dentro = dentro[:total]
    piso = dentro[0][0] if dentro else -1.0
    restante = sorted((t for t in restante if t[0] > piso), key=lambda t: -t[0])[:fora]
    return dentro, restante, nao_encontrados


def formatar_trechos(achados):
    return "\n\n---\n\n".join(
        f"[{base} · {p['arquivo']}, página {p['pagina']}]\n{p['texto']}"
        for _, p, base in achados)
