import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from ...domain.conversa import ASSISTENTE, USUARIO, Mensagem
from ...domain.erros import (ArquivoInvalido, ArquivoRepetido, AtualizacaoEmAndamento, BancaOcupada,
                             BlocoInexistente, DocumentoDesconhecido, FalaVazia, NenhumaBaseDisponivel,
                             PerguntaVazia, RespostaInvalida, VozIndisponivel)

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
    @app.exception_handler(AtualizacaoEmAndamento)
    @app.exception_handler(ArquivoRepetido)
    def ocupada(_, erro):
        return JSONResponse({"erro": str(erro)}, status_code=409)

    @app.exception_handler(DocumentoDesconhecido)
    @app.exception_handler(BlocoInexistente)
    def desconhecido(_, erro):
        return JSONResponse({"erro": str(erro)}, status_code=404)

    @app.exception_handler(ArquivoInvalido)
    def arquivo_invalido(_, erro):
        return JSONResponse({"erro": str(erro)}, status_code=400)

    @app.exception_handler(VozIndisponivel)
    def sem_voz(_, erro):
        return JSONResponse({"erro": str(erro)}, status_code=502)

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

    @app.get("/biblioteca", response_class=HTMLResponse)
    def pagina_biblioteca():
        return _pagina("biblioteca.html")

    @app.get("/biblioteca/documentos")
    def documentos():
        return {"documentos": [d.como_dict() for d in container.biblioteca.documentos()],
                "pendentes": container.biblioteca.pendentes(),
                "bases": list(container.biblioteca.bases()),
                "vozes": list(container.narrador.vozes())}

    @app.get("/biblioteca/documentos/{referencia}")
    def documento(referencia: str):
        aberto, blocos = container.biblioteca.abrir(referencia)
        return {**aberto.como_dict(), "blocos": [b.como_dict() for b in blocos]}

    @app.get("/biblioteca/documentos/{referencia}/pdf")
    def pdf(referencia: str):
        caminho = container.biblioteca.pdf(referencia)
        if caminho is None:
            return JSONResponse({"erro": "o PDF original não está neste computador"}, status_code=404)
        return FileResponse(caminho, media_type="application/pdf", content_disposition_type="inline",
                            filename=Path(caminho).name)

    @app.get("/biblioteca/documentos/{referencia}/audio/{numero}")
    def audio(referencia: str, numero: int, voz: Optional[str] = None):
        return Response(container.narrador.narrar(referencia, numero, voz), media_type="audio/mpeg",
                        headers={"Cache-Control": "private, max-age=86400"})

    @app.post("/biblioteca/enviar")
    async def enviar(request: Request, base: str, nome: str):
        return {"ok": True, "arquivo": container.biblioteca.guardar(base, nome, await request.body())}

    @app.post("/biblioteca/atualizar", status_code=202)
    def atualizar():
        container.atualizacao.iniciar()
        return {"ok": True}

    @app.get("/biblioteca/atualizacao")
    def atualizacao():
        return container.atualizacao.estado()

    return app
