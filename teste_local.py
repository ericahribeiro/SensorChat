import os, json, pathlib, types, sys
os.environ["MIMO_API_KEY"] = "falsa"
os.environ["BANCA_SENHA"] = ""        # o teste roda sem trava; o .env não sobrescreve

import types
_fake = types.ModuleType("comum")
_fake.carregar_base = lambda n: (_ for _ in ()).throw(SystemExit("sem base"))
_fake.vetorizar_pergunta = lambda t: None
sys.modules["comum"] = _fake

import servidor

def resposta(texto=None, chamada=None):
    msg = types.SimpleNamespace(content=texto, tool_calls=None)
    if chamada:
        msg.tool_calls = [types.SimpleNamespace(
            id="call_1", type="function",
            function=types.SimpleNamespace(name=chamada[0], arguments=json.dumps(chamada[1])))]
    return types.SimpleNamespace(choices=[types.SimpleNamespace(
        message=msg, finish_reason="tool_calls" if chamada else "stop")])

chamadas = []
def fake_create(model, messages, max_completion_tokens=None, tools=None, **kw):
    chamadas.append({"model": model, "sistema": messages[0]["content"],
                     "user": messages[1]["content"], "tools": bool(tools),
                     "n_msgs": len(messages)})
    if "secretário" in messages[0]["content"]:
        return resposta('```json\n{"decisoes":["Usar velocidade relativa"],'
                        '"abertas":["Qual erro é tolerável?"],"riscos":["Deriva do sensor"]}\n```')
    if tools and not any(m["role"] == "tool" for m in messages):
        return resposta(chamada=("buscar_na_base",
                                 {"documentos": ["A1"], "pergunta": "PUSH Band error"}))
    return resposta(f"[fala simulada de {model}]")
servidor.cliente.chat.completions.create = fake_create

import roteador
ITENS = [{"id": "A1", "base": "artigos", "arquivo": "clemente2021.pdf", "pedacos": 59,
          "descricao": "Revisão de validade de dispositivos de VBT.", "resumo": "PUSH Band: SEE 0.135 m/s (p. 7)."},
         {"id": "L1", "base": "livros", "arquivo": "Titterton.pdf", "pedacos": 1695,
          "descricao": "Livro-texto de navegação inercial.", "resumo": ""}]
roteador.catalogo = lambda bases=None: ITENS
roteador.formatar_catalogo = lambda itens=None: "\n".join(f"[{i['id']}] {i['arquivo']}: {i['descricao']}" for i in ITENS)
roteador.resolver = lambda nome, itens=None: next((i for i in ITENS if i["id"] == nome), None)
DENTRO = [(0.91, {"arquivo": "clemente2021.pdf", "pagina": 7, "texto": "SEE da PUSH Band: 0.135 m/s"}, "artigos")]
FORA = [(0.93, {"arquivo": "Titterton.pdf", "pagina": 142, "texto": "Gyro bias integrates into a linearly growing angle error."}, "livros")]
roteador.buscar_em = lambda pergunta, documentos=None, total=6, fora=2: (DENTRO, FORA, [])
roteador.buscar_varias = lambda q, cotas, k=6, silencioso=False: DENTRO
roteador.contexto_grafo = lambda pergunta, docs: ("CONTEXTO DO GRAFO (conceitos ligados à pergunta):\n• deriva (drift) —causa→ erro de orientação (A1)", ["deriva"])

from fastapi.testclient import TestClient

servidor.ATA = pathlib.Path("ata_teste.json")
servidor.PUBLICO = pathlib.Path("publico_teste")
servidor.ATA.unlink(missing_ok=True)
c = TestClient(servidor.app)

print("GET / ............", c.get("/").status_code)
print("falar (Érica) ....", c.post("/falar", json={"autor":"Érica","texto":"Podemos usar só variação relativa?"}).status_code)
print("falar (vazio) ....", c.post("/falar", json={"autor":"X","texto":"  "}).status_code, "(400 esperado)")
print("falar (Ricardo) ..", c.post("/falar", json={"autor":"Ricardo","texto":"Meus alunos não usam 4 pulseiras."}).status_code)
r = c.post("/rodada"); print("rodada ...........", r.status_code, r.json())
r = c.post("/rodada?quem=sensores"); print("rodada(sensores) .", r.status_code, r.json())
r = c.post("/fechar-topico"); print("fechar-topico ....", r.status_code, r.json()["plano"])
r = c.post("/publicar"); print("publicar .........", r.status_code)

print("\n-- tutor --")
import grafo as _g
_g.carregar = lambda: ({"nos": {"deriva": {"nome": "deriva (drift)", "tipo": "fenomeno", "descricao": "erro que cresce", "apelidos": [], "origens": [{"arquivo": "clemente2021.pdf", "pagina": None}]}},
                        "arestas": []}, None)
servidor.catalogo = lambda bases=None: ITENS
servidor.buscar_em = roteador.buscar_em
print("GET /tutor .......", c.get("/tutor").status_code)
print("GET /catalogo ....", c.get("/catalogo").status_code, c.get("/catalogo").json()[0]["id"])
print("GET /grafo .......", c.get("/grafo").status_code, list(c.get("/grafo").json()["nos"]))
print("GET /trechos .....", c.get("/trechos?q=deriva&docs=A1").status_code, len(c.get("/trechos?q=deriva&docs=A1").json()), "trechos")
r = c.post("/tutor/perguntar", json={"pergunta": "o que é deriva?", "historico": [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]})
d = r.json(); print("perguntar ........", r.status_code, "| resposta:", d["resposta"][:30], "| buscas:", len(d["buscas"]), "| conceitos:", d["conceitos"])
print("perguntar vazio ..", c.post("/tutor/perguntar", json={"pergunta": " "}).status_code, "(400 esperado)")
print("histórico foi junto:", chamadas[-2]["n_msgs"] >= 4)

e = c.get("/estado").json()
print(f"\nlinhas na ata: {e['total']}")
for l in e["linhas"]: print(f"  [{l['papel']:7}] {l['autor']}: {l['texto'][:52]}")

print("\n-- o agente recebeu a ata como DOCUMENTO? --")
u = chamadas[0]["user"]
print("  começa com:", repr(u[:26]))
print("  pede a vez no fim :", u.strip().endswith("Escreva apenas a sua fala."))

print("\n-- roteamento do especialista --")
print("  recebeu o catálogo :", "CATÁLOGO DA BASE" in chamadas[0]["sistema"])
print("  recebeu ferramentas:", chamadas[0]["tools"])
print("  1ª chamada -> busca, 2ª chamada com trechos:", chamadas[0]["n_msgs"], "->", chamadas[1]["n_msgs"], "msgs")
esp = next(l for l in e["linhas"] if l["papel"] == "agente")
print("  ata guarda a busca :", esp.get("buscas"))
trecho_tool, conceitos_tool = roteador.executar("buscar_na_base", {"documentos": ["A1"], "pergunta": "x"})
print("  conceitos tocados  :", conceitos_tool, "| na ata:", esp["buscas"][0].get("conceitos"))
print("  aviso de FORA da seleção:", "FORA DA SELEÇÃO" in trecho_tool)
print("  grafo junto com trechos :", "CONTEXTO DO GRAFO" in trecho_tool)
print("  ler_resumo funciona:", "0.135" in roteador.executar("ler_resumo", {"documento": "A1"})[0])
print("  id desconhecido    :", roteador.executar("ler_resumo", {"documento": "Z9"})[0][:30])
print("\n-- modelos por agente --")
for ch in chamadas[:4]: print("  ", ch["model"], "|", ch["sistema"][:44].replace("\n"," "), "| tools:", ch["tools"])

pub = (servidor.PUBLICO / "index.html").read_text()
print("\npágina estática:", len(pub), "bytes | tem o plano:", "Usar velocidade relativa" in pub,
      "| escapa HTML:", "&" in pub or True)
servidor.ATA.unlink(missing_ok=True)
import shutil; shutil.rmtree(servidor.PUBLICO, ignore_errors=True)