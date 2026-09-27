import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from ...domain.conversa import ASSISTENTE, USUARIO, Mensagem
from ...domain.erros import BancaOcupada, FalaVazia, NenhumaBaseDisponivel, PerguntaVazia, RespostaInvalida

PAGINAS = Path(__file__).parent / "paginas"


class Fala(BaseModel):
    autor: str
    texto: str


class Pergunta(BaseModel):
    pergunta: str
    historico: list = []


def _pagina(nome):
    return (PAGINAS / nome).read_text(encoding="utf-8")


def _autenticacao(configuracao):
    basica = HTTPBasic(auto_error=False)

    def conferir_senha(credenciais: Optional[HTTPBasicCredentials] = Depends(basica)):
        if not configuracao.banca_senha:
            return
        negar = HTTPException(status_code=401, detail="senha incorreta",
                              headers={"WWW-Authenticate": "Basic"})
        if credenciais is None:
            raise negar
        if not (secrets.compare_digest(credenciais.username, configuracao.banca_usuario)
                and secrets.compare_digest(credenciais.password, configuracao.banca_senha)):
            raise negar

    return conferir_senha


def _registrar_erros(app):
    @app.exception_handler(FalaVazia)
    @app.exception_handler(PerguntaVazia)
    def vazio(_, __):
        return JSONResponse({"erro": "vazio"}, status_code=400)

    @app.exception_handler(BancaOcupada)
    def ocupada(_, erro):
        return JSONResponse({"erro": str(erro)}, status_code=409)

    @app.exception_handler(RespostaInvalida)
    def invalida(_, erro):
        return JSONResponse({"erro": "o resumidor não devolveu JSON", "bruto": erro.bruto[:400]},
                            status_code=502)


def _historico(mensagens):
    return [Mensagem(m["role"], str(m.get("content", ""))) for m in mensagens
            if isinstance(m, dict) and m.get("role") in (USUARIO, ASSISTENTE)]


def criar_app(container):
    app = FastAPI(dependencies=[Depends(_autenticacao(container.configuracao))])
    _registrar_erros(app)

    @app.get("/", response_class=HTMLResponse)
    def pagina_banca():
        return _pagina("banca.html")

    @app.get("/estado")
    def estado(desde: int = 0):
        atual = container.banca.estado(desde)
        return {"linhas": [l.como_dict() for l in atual.linhas], "total": atual.total,
                "plano": atual.plano.como_dict(), "ocupado": atual.ocupada}

    @app.post("/falar")
    def falar(fala: Fala):
        container.banca.registrar_fala(fala.autor, fala.texto)
        return {"ok": True}

    @app.post("/rodada")
    def rodada(quem: Optional[str] = None):
        return {"ok": True, "falaram": container.banca.rodada(quem)}

    @app.post("/fechar-topico")
    def fechar_topico():
        return {"ok": True, "plano": container.banca.fechar_topico().como_dict()}

    @app.post("/publicar")
    def publicar():
        return {"ok": True, "arquivo": container.banca.publicar()}

    @app.get("/tutor", response_class=HTMLResponse)
    def pagina_tutor():
        return _pagina("tutor.html")

    @app.post("/tutor/perguntar")
    def perguntar(pergunta: Pergunta):
        resposta = container.tutor.perguntar(pergunta.pergunta, _historico(pergunta.historico))
        return {"resposta": resposta.resposta,
                "buscas": [c.como_dict() for c in resposta.consultas],
                "conceitos": resposta.conceitos}

    @app.get("/catalogo")
    def catalogo():
        return [{"id": d.id, "base": d.base, "arquivo": d.arquivo,
                 "pedacos": d.pedacos, "descricao": d.descricao}
                for d in container.busca.catalogo()]

    @app.get("/grafo")
    def grafo():
        atual = container.consulta_grafo.grafo()
        return atual.como_dict() if atual else {"nos": {}, "arestas": []}

    @app.get("/trechos")
    def trechos(q: str, docs: str = ""):
        ids = [d for d in docs.split(",") if d.strip()]
        try:
            resultado = container.busca.buscar_em(q, ids or None, total=4)
        except NenhumaBaseDisponivel:
            return []
        por_arquivo = container.busca.catalogo().ids_por_arquivo()
        return [{"id": por_arquivo.get(t.pedaco.arquivo, "?"), "arquivo": t.pedaco.arquivo,
                 "pagina": t.pedaco.pagina, "texto": t.pedaco.texto, "nota": round(t.nota, 3)}
                for t in resultado.dentro]

    return app
