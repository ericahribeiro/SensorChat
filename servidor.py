import os, json, threading, pathlib, datetime, html
from typing import Optional

import secrets
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from openai import OpenAI

from agentes import AGENTES, ORDEM_DA_RODADA, RESUMIDOR
from roteador import responder_com_busca, bloco_catalogo
from busca_multi import catalogo, buscar_em, resolver
import grafo
import tutor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
ATA = pathlib.Path("ata.json")
PUBLICO = pathlib.Path("publico")

if not API_KEY:
    raise SystemExit("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")

SENHA = os.environ.get("BANCA_SENHA", "")
USUARIO = os.environ.get("BANCA_USUARIO", "banca")
_basica = HTTPBasic(auto_error=False)


def conferir_senha(cred: Optional[HTTPBasicCredentials] = Depends(_basica)):
    if not SENHA:
        return
    negar = HTTPException(status_code=401, detail="senha incorreta",
                          headers={"WWW-Authenticate": "Basic"})
    if cred is None:
        raise negar
    if not (secrets.compare_digest(cred.username, USUARIO)
            and secrets.compare_digest(cred.password, SENHA)):
        raise negar

cliente = OpenAI(api_key=API_KEY, base_url=BASE_URL)
_trava = threading.Lock()

_banca_falando = threading.Lock()

SEM_RACIOCINIO = {"thinking": {"type": "disabled"}}


def texto_completo(r):
    escolha = r.choices[0]
    texto = (escolha.message.content or "").strip()
    if escolha.finish_reason == "length" or not texto:
        texto += "\n\n[fala interrompida: estourou o limite de tokens]"
    return texto


def estado_vazio():
    return {"linhas": [], "plano": {"decisoes": [], "abertas": [], "riscos": []}}


def ler():
    if ATA.exists():
        return json.loads(ATA.read_text(encoding="utf-8"))
    return estado_vazio()


def gravar(estado):
    tmp = ATA.with_suffix(".tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ATA)


def acrescentar(autor, papel, texto, buscas=None):
    with _trava:
        estado = ler()
        linha = {
            "n": len(estado["linhas"]),
            "autor": autor,
            "papel": papel,
            "texto": texto.strip(),
            "quando": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        if buscas:
            linha["buscas"] = buscas
        estado["linhas"].append(linha)
        gravar(estado)
        return estado


def ata_em_texto(linhas, limite=60):
    return "\n\n".join(f"{l['autor']}: {l['texto']}" for l in linhas[-limite:])


def turno(chave):
    ag = AGENTES[chave]
    estado = ler()
    ata_txt = ata_em_texto(estado["linhas"])

    conteudo = (f"ATA DA REUNIÃO ATÉ AGORA\n\n{ata_txt}\n\n---\n\n"
                f"É a sua vez de falar, como {ag['nome']}. Escreva apenas a sua fala.")

    if not ag.get("usa_rag"):
        r = cliente.chat.completions.create(
            model=ag["modelo"],
            messages=[{"role": "system", "content": ag["sistema"]},
                      {"role": "user", "content": conteudo}],
            max_completion_tokens=700,
            extra_body=SEM_RACIOCINIO,
        )
        return acrescentar(ag["nome"], "agente", texto_completo(r))

    ultima = next((l["texto"] for l in reversed(estado["linhas"])
                   if l["papel"] == "humano"), "")
    r, buscas = responder_com_busca(
        cliente, ag["modelo"],
        [{"role": "system", "content": ag["sistema"] + bloco_catalogo()},
         {"role": "user", "content": conteudo}],
        max_tokens=700, extra_body=SEM_RACIOCINIO,
        busca_cega=ultima or ata_txt[-500:], cotas=ag.get("cotas"))
    return acrescentar(ag["nome"], "agente", texto_completo(r), buscas)

app = FastAPI(dependencies=[Depends(conferir_senha)])


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
            "plano": estado["plano"],
            "ocupado": _banca_falando.locked()}


@app.post("/falar")
def falar(f: Fala):
    if not f.texto.strip():
        return JSONResponse({"erro": "vazio"}, status_code=400)
    acrescentar(f.autor.strip() or "Anônimo", "humano", f.texto)
    return {"ok": True}


@app.post("/rodada")
def rodada(quem: Optional[str] = None):
    if not _banca_falando.acquire(blocking=False):
        return JSONResponse({"erro": "a banca já está falando"}, status_code=409)
    try:
        alvos = [quem] if quem in AGENTES else ORDEM_DA_RODADA
        for chave in alvos:
            turno(chave)
        return {"ok": True, "falaram": alvos}
    finally:
        _banca_falando.release()


@app.post("/fechar-topico")
def fechar_topico():
    if not _banca_falando.acquire(blocking=False):
        return JSONResponse({"erro": "a banca já está falando"}, status_code=409)
    try:
        return _fechar_topico()
    finally:
        _banca_falando.release()


def _fechar_topico():
    estado = ler()
    r = cliente.chat.completions.create(
        model="mimo-v2.5",
        messages=[{"role": "system", "content": RESUMIDOR},
                  {"role": "user", "content": ata_em_texto(estado["linhas"], limite=200)}],
        max_completion_tokens=900,
        extra_body=SEM_RACIOCINIO,
    )
    bruto = texto_completo(r).strip()
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


class Pergunta(BaseModel):
    pergunta: str
    historico: list = []


@app.get("/tutor", response_class=HTMLResponse)
def pagina_tutor():
    return pathlib.Path("tutor.html").read_text(encoding="utf-8")


@app.post("/tutor/perguntar")
def tutor_perguntar(p: Pergunta):
    if not p.pergunta.strip():
        return JSONResponse({"erro": "vazio"}, status_code=400)
    historico = [{"role": m["role"], "content": str(m["content"])}
                 for m in p.historico if m.get("role") in ("user", "assistant")]
    resposta, buscas, conceitos = tutor.responder(cliente, historico, p.pergunta.strip())
    return {"resposta": resposta, "buscas": buscas, "conceitos": conceitos}


@app.get("/catalogo")
def get_catalogo():
    return [{k: it[k] for k in ("id", "base", "arquivo", "pedacos", "descricao")}
            for it in catalogo()]


@app.get("/grafo")
def get_grafo():
    g, _ = grafo.carregar()
    return g or grafo.vazio()


@app.get("/trechos")
def get_trechos(q: str, docs: str = ""):
    ids = [d for d in docs.split(",") if d.strip()]
    try:
        dentro, _, _ = buscar_em(q, ids or None, total=4)
    except SystemExit:
        return []
    por_arquivo = {it["arquivo"]: it["id"] for it in catalogo()}
    return [{"id": por_arquivo.get(p["arquivo"], "?"), "arquivo": p["arquivo"],
             "pagina": p["pagina"], "texto": p["texto"], "nota": round(n, 3)}
            for n, p, _ in dentro]


@app.post("/publicar")
def publicar():
    estado = ler()
    PUBLICO.mkdir(exist_ok=True)
    e = html.escape

    def lista(itens):
        return "".join(f"<li>{e(i)}</li>" for i in itens) or "<li class=v>—</li>"

    def consultas(l):
        if not l.get("buscas"):
            return ""
        itens = "; ".join(f"{', '.join(b['documentos'])} — «{b['pergunta']}»" if b["pergunta"]
                          else ", ".join(b["documentos"]) for b in l["buscas"])
        arquivos = "\n".join(a for b in l["buscas"] for a in b.get("arquivos", []))
        return f'<small title="{e(arquivos)}">consultou: {e(itens)}</small>'

    linhas = "".join(
        f'<div class="l {l["papel"]}"><b>{e(l["autor"])}</b>'
        f'<time>{e(l["quando"][11:16])}</time><p>{e(l["texto"])}</p>{consultas(l)}</div>'
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
 .l p{{margin:6px 0 0;white-space:pre-wrap}} .l small{{display:block;margin-top:6px;color:#8b949e;font-size:.76rem}}
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