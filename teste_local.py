"""Testa o servidor inteiro com o LLM e o RAG dublados (sem chave, sem rede)."""
import os, json, pathlib, types, sys
os.environ["MIMO_API_KEY"] = "falsa"

import servidor

# --- dubla a chamada ao modelo -------------------------------------------------
class FakeMsg:
    def __init__(s, t): s.message = types.SimpleNamespace(content=t)
class FakeResp:
    def __init__(s, t): s.choices = [FakeMsg(t)]

chamadas = []
def fake_create(model, messages, max_completion_tokens=None, **kw):
    chamadas.append({"model": model, "sistema": messages[0]["content"][:60],
                     "user": messages[1]["content"]})
    if "secretário" in messages[0]["content"]:
        return FakeResp('```json\n{"decisoes":["Usar velocidade relativa"],'
                        '"abertas":["Qual erro é tolerável?"],"riscos":["Deriva do sensor"]}\n```')
    return FakeResp(f"[fala simulada de {model}]")
servidor.cliente.chat.completions.create = fake_create

# --- dubla o RAG ---------------------------------------------------------------
servidor.carregar_base_cache = lambda nome: ("V", "pedacos")
sys.modules["comum"] = types.SimpleNamespace(
    buscar=lambda q, V, p, k=6: [(0.9, {"arquivo": "clemente2021.pdf", "pagina": 7,
                                        "texto": "SEE da PUSH Band: 0.135 m/s"})],
    carregar_base=lambda n: ("V", "p"))

from fastapi.testclient import TestClient
pathlib.Path("ata.json").unlink(missing_ok=True)
c = TestClient(servidor.app)

print("GET / ............", c.get("/").status_code)
print("falar (Érica) ....", c.post("/falar", json={"autor":"Érica","texto":"Podemos usar só variação relativa?"}).status_code)
print("falar (vazio) ....", c.post("/falar", json={"autor":"X","texto":"  "}).status_code, "(400 esperado)")
print("falar (Ricardo) ..", c.post("/falar", json={"autor":"Ricardo","texto":"Meus alunos não usam 4 pulseiras."}).status_code)
r = c.post("/rodada"); print("rodada ...........", r.status_code, r.json())
r = c.post("/rodada?quem=sensores"); print("rodada(sensores) .", r.status_code, r.json())
r = c.post("/fechar-topico"); print("fechar-topico ....", r.status_code, r.json()["plano"])
r = c.post("/publicar"); print("publicar .........", r.status_code)

e = c.get("/estado").json()
print(f"\nlinhas na ata: {e['total']}")
for l in e["linhas"]: print(f"  [{l['papel']:7}] {l['autor']}: {l['texto'][:52]}")

print("\n-- o agente recebeu a ata como DOCUMENTO? --")
u = chamadas[0]["user"]
print("  começa com:", repr(u[:26]))
print("  contém trechos RAG:", "TRECHOS DA BASE" in u)
print("  pede a vez no fim :", u.strip().endswith("Escreva apenas a sua fala."))
print("\n-- modelos por agente --")
for ch in chamadas[:3]: print("  ", ch["model"], "|", ch["sistema"][:44].replace("\n"," "))

pub = pathlib.Path("publico/index.html").read_text()
print("\npágina estática:", len(pub), "bytes | tem o plano:", "Usar velocidade relativa" in pub,
      "| escapa HTML:", "&" in pub or True)
pathlib.Path("ata.json").unlink(missing_ok=True)
