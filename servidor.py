import os, json, time, threading, pathlib, datetime, html
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from openai import OpenAI

from agentes import AGENTES, ORDEM_DA_RODADA, RESUMIDOR

# Lê o arquivo .env (que NUNCA vai para o git). Sem ele, usa as variáveis
# de ambiente normais. A chave nunca fica escrita no código.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
ATA = pathlib.Path("ata.json")
PUBLICO = pathlib.Path("publico")
TRECHOS_POR_TURNO = 6

if not API_KEY:
    raise SystemExit("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")

cliente = OpenAI(api_key=API_KEY, base_url=BASE_URL)
_trava = threading.Lock()

_bases = {}


def carregar_base_cache(nome):
    if nome not in _bases:
        from comum import carregar_base
        _bases[nome] = carregar_base(nome)
    return _bases[nome]


# --------------------------------------------------------------------------
# ESTADO
# --------------------------------------------------------------------------
def estado_vazio():
    return {"linhas": [], "plano": {"decisoes": [], "abertas": [], "riscos": []}}


def ler():
    if ATA.exists():
        return json.loads(ATA.read_text(encoding="utf-8"))
    return estado_vazio()


def gravar(estado):
    tmp = ATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ATA)          # escrita atômica: nunca deixa ata.json pela metade


def acrescentar(autor, papel, texto):
    with _trava:
        estado = ler()
        estado["linhas"].append({
            "n": len(estado["linhas"]),
            "autor": autor,
            "papel": papel,             # "humano" ou "agente"
            "texto": texto.strip(),
            "quando": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        gravar(estado)
        return estado


def ata_em_texto(linhas, limite=60):
    return "\n\n".join(f"{l['autor']}: {l['texto']}" for l in linhas[-limite:])


# --------------------------------------------------------------------------
# TURNO DE UM AGENTE
# --------------------------------------------------------------------------
def turno(chave):
    ag = AGENTES[chave]
    estado = ler()
    ata_txt = ata_em_texto(estado["linhas"])

    contexto = ""
    if ag["usa_rag"]:
        try:
            from comum import buscar
            V, pedacos = carregar_base_cache(ag["base"])
            ultima = next((l["texto"] for l in reversed(estado["linhas"])
                           if l["papel"] == "humano"), "")
            achados = buscar(ultima or ata_txt[-500:], V, pedacos, TRECHOS_POR_TURNO)
            contexto = "\n\nTRECHOS DA BASE:\n\n" + "\n\n---\n\n".join(
                f"[{p['arquivo']}, página {p['pagina']}]\n{p['texto']}" for _, p in achados)
        except SystemExit:
            contexto = "\n\n(A base de artigos não está indexada. Diga isso em vez de inventar.)"

    # A ata vai como DOCUMENTO, não como fala dirigida ao modelo. É isso que
    # impede o agente de tratar quem escreveu como alguém a ser agradado.
    conteudo = (f"ATA DA REUNIÃO ATÉ AGORA\n\n{ata_txt}{contexto}\n\n---\n\n"
                f"É a sua vez de falar, como {ag['nome']}. Escreva apenas a sua fala.")

    r = cliente.chat.completions.create(
        model=ag["modelo"],
        messages=[{"role": "system", "content": ag["sistema"]},
                  {"role": "user", "content": conteudo}],
        max_completion_tokens=700,
    )
    return acrescentar(ag["nome"], "agente", r.choices[0].message.content)


# --------------------------------------------------------------------------
# ROTAS
# --------------------------------------------------------------------------
app = FastAPI()


class Fala(BaseModel):
    autor: str
    texto: str


@app.get("/", response_class=HTMLResponse)
def pagina():
    return pathlib.Path("banca.html").read_text(encoding="utf-8")


@app.get("/estado")
def get_estado(desde: int = 0):
    estado = ler()
    return {"linhas": estado["linhas"][desde:],
            "total": len(estado["linhas"]),
            "plano": estado["plano"]}


@app.post("/falar")
def falar(f: Fala):
    if not f.texto.strip():
        return JSONResponse({"erro": "vazio"}, status_code=400)
    acrescentar(f.autor.strip() or "Anônimo", "humano", f.texto)
    return {"ok": True}


@app.post("/rodada")
def rodada(quem: Optional[str] = None):
    alvos = [quem] if quem in AGENTES else ORDEM_DA_RODADA
    for chave in alvos:
        turno(chave)
    return {"ok": True, "falaram": alvos}


@app.post("/fechar-topico")
def fechar_topico():
    estado = ler()
    r = cliente.chat.completions.create(
        model="mimo-v2.5",
        messages=[{"role": "system", "content": RESUMIDOR},
                  {"role": "user", "content": ata_em_texto(estado["linhas"], limite=200)}],
        max_completion_tokens=900,
    )
    bruto = r.choices[0].message.content.strip()
    bruto = bruto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        plano = json.loads(bruto)
    except json.JSONDecodeError:
        return JSONResponse({"erro": "o resumidor não devolveu JSON", "bruto": bruto[:400]},
                            status_code=502)
    with _trava:
        estado = ler()
        estado["plano"] = plano
        gravar(estado)
    return {"ok": True, "plano": plano}


@app.post("/publicar")
def publicar():
    """Gera um HTML estático da ata + plano, para hospedar em lugar que fica sempre no ar."""
    estado = ler()
    PUBLICO.mkdir(exist_ok=True)
    e = html.escape

    def lista(itens):
        return "".join(f"<li>{e(i)}</li>" for i in itens) or "<li class=v>—</li>"

    linhas = "".join(
        f'<div class="l {l["papel"]}"><b>{e(l["autor"])}</b>'
        f'<time>{e(l["quando"][11:16])}</time><p>{e(l["texto"])}</p></div>'
        for l in estado["linhas"])

    doc = f"""<!doctype html><meta charset=utf-8>
<title>Banca — ata e plano</title>
<style>
 body{{font:16px/1.7 -apple-system,system-ui,sans-serif;max-width:820px;margin:0 auto;
 padding:32px 20px 80px;background:#f4f5f7;color:#1e2228}}
 h1{{font-size:1.7rem;margin:0 0 4px}} h2{{font-size:1.1rem;margin:32px 0 10px}}
 .meta{{color:#6a737d;font-size:.85rem;margin-bottom:28px}}
 .plano{{background:#fff;border:1px solid #dfe3e8;border-radius:4px;padding:18px 22px}}
 ul{{margin:6px 0 16px;padding-left:20px}} li{{margin:3px 0}} .v{{color:#8b949e;list-style:none;margin-left:-20px}}
 .l{{background:#fff;border:1px solid #dfe3e8;border-left:3px solid #c8ced6;
 border-radius:0 4px 4px 0;padding:12px 16px;margin:8px 0}}
 .l.agente{{border-left-color:#4a3ea8;background:#fbfbfe}}
 .l b{{font-size:.9rem}} .l time{{color:#8b949e;font-size:.78rem;margin-left:8px}}
 .l p{{margin:6px 0 0;white-space:pre-wrap}}
 @media(prefers-color-scheme:dark){{body{{background:#15171b;color:#e6e9ee}}
 .plano,.l{{background:#1d2026;border-color:#2e333b}} .l.agente{{background:#1f1f2b}}}}
</style>
<h1>Banca — ata e plano</h1>
<div class=meta>Gerado em {datetime.datetime.now():%d/%m/%Y às %H:%M} · {len(estado["linhas"])} falas</div>
<div class=plano>
 <h2 style="margin-top:0">Decisões</h2><ul>{lista(estado["plano"]["decisoes"])}</ul>
 <h2>Em aberto</h2><ul>{lista(estado["plano"]["abertas"])}</ul>
 <h2>Riscos</h2><ul>{lista(estado["plano"]["riscos"])}</ul>
</div>
<h2>Ata</h2>{linhas}"""
    destino = PUBLICO / "index.html"
    destino.write_text(doc, encoding="utf-8")
    return {"ok": True, "arquivo": str(destino.resolve())}
