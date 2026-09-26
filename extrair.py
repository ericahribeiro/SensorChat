
import os, sys, json, re, unicodedata, pathlib
import numpy as np
from openai import OpenAI

from comum import carregar_base, vetorizar_documentos
from busca_multi import CATALOGO
from grafo import GRAFO_JSON, GRAFO_NPZ, vazio

EXTRACOES = pathlib.Path("extracoes.json")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
MODELO = "mimo-v2.5"

LIMIAR_FUSAO = 0.96
PALAVRAS_VAZIAS = {"de", "da", "do", "das", "dos", "com", "para", "por", "em", "the", "of"}
TIPOS = "conceito, dispositivo, metodo, metrica, grandeza, exercicio, segmento_corporal, fenomeno"

INSTRUCOES = f"""Extraia do texto um grafo de conceitos sobre sensores inerciais, biomecânica
e treino de força. Devolva JSON puro, sem cerca de código:

{{"entidades": [{{"nome": "...", "tipo": "...", "descricao": "..."}}],
 "relacoes": [{{"de": "...", "para": "...", "relacao": "..."}}]}}

Regras:
- nome em português, com o termo em inglês entre parênteses quando existir:
  "deriva (drift)", "unidade de medição inercial (IMU)". Singular, minúsculas.
- tipo: um de {TIPOS}.
- descricao: uma frase, com número se o texto der ("SEE de 0,135 m/s").
- relacao: verbo curto em português: causa, corrige, mede, estima, depende de,
  compara com, valida contra, compõe, limita, requer, aplica-se a.
- só o que está no texto. Nada de conhecimento geral. No máximo 12 entidades
  e 15 relações por texto; escolha as que carregam a ideia central."""


def slug(nome):
    s = unicodedata.normalize("NFKD", nome.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def partes(nome):
    fora = re.sub(r"\(.*?\)", " ", nome).strip()
    dentro = re.findall(r"\((.*?)\)", nome)
    sigla = slug(dentro[0]) if dentro else None
    tokens = {t.rstrip("s") for t in slug(fora).split("-")
              if len(t) >= 4 and t not in PALAVRAS_VAZIAS}
    return slug(fora), sigla, tokens


def extrair(cliente, texto):
    r = cliente.chat.completions.create(
        model=MODELO,
        messages=[{"role": "system", "content": INSTRUCOES},
                  {"role": "user", "content": texto}],
        max_completion_tokens=1500,
        extra_body={"thinking": {"type": "disabled"}},
    )
    bruto = (r.choices[0].message.content or "").strip()
    bruto = bruto.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    d = json.loads(bruto)
    return d.get("entidades", []), d.get("relacoes", [])


class Grafo:

    def __init__(self, g, V):
        self.g = g
        self.ids = list(g["nos"])
        self.V = V if V is not None else np.zeros((0, 768), "float32")
        self.por_chave, self.por_sigla, self.tokens, self.siglas = {}, {}, {}, {}
        for nid, no in g["nos"].items():
            for nome in [no["nome"]] + no.get("apelidos", []):
                self._registrar(nid, nome)

    def _registrar(self, nid, nome):
        chave, sigla, toks = partes(nome)
        self.por_chave.setdefault(chave, nid)
        if sigla:
            self.por_sigla.setdefault(sigla, nid)
            self.siglas.setdefault(nid, set()).add(sigla)
        if toks:
            self.tokens.setdefault(nid, []).append(toks)
    def _achar(self, nome, v):
        chave, sigla, toks = partes(nome)
        if chave in self.por_chave:
            return self.por_chave[chave]
        if sigla and sigla in self.por_sigla:
            return self.por_sigla[sigla]
        if len(self.ids) and toks:
            notas = self.V @ v
            for j in np.argsort(-notas)[:5]:
                if notas[j] < LIMIAR_FUSAO:
                    break
                nid = self.ids[j]
                if sigla and self.siglas.get(nid) and sigla not in self.siglas[nid]:
                    continue
                for outros in self.tokens.get(nid, []):
                    if toks <= outros or outros <= toks:
                        return nid
        return None

    def _vetores(self, nomes):
        return vetorizar_documentos(nomes, lote=64) if nomes else np.zeros((0, 768), "float32")

    def incorporar(self, entidades, relacoes, origem):
        nomes = [e["nome"].strip() for e in entidades if e.get("nome")]
        if not nomes:
            return
        vs = self._vetores(nomes)
        mapa = {}
        for e, v in zip(entidades, vs):
            nome = e["nome"].strip()
            alvo = self._achar(nome, v)
            if alvo is None:
                alvo = slug(nome) or f"no-{len(self.ids)}"
                while alvo in self.g["nos"]:
                    alvo += "-"
                self.g["nos"][alvo] = {"nome": nome, "tipo": e.get("tipo", "conceito"),
                                       "descricao": e.get("descricao", "").strip(),
                                       "apelidos": [], "origens": []}
                self.ids.append(alvo)
                self.V = np.vstack([self.V, v[None]])
            self._registrar(alvo, nome)
            no = self.g["nos"][alvo]
            if nome != no["nome"] and nome not in no["apelidos"]:
                no["apelidos"].append(nome)
            if not no["descricao"] and e.get("descricao"):
                no["descricao"] = e["descricao"].strip()
            if origem not in no["origens"]:
                no["origens"].append(origem)
            mapa[nome.lower()] = alvo

        existentes = {(a["de"], a["para"], a["relacao"]): a for a in self.g["arestas"]}
        for r in relacoes:
            de = mapa.get((r.get("de") or "").strip().lower())
            para = mapa.get((r.get("para") or "").strip().lower())
            rel = (r.get("relacao") or "").strip().lower()
            if not de or not para or de == para or not rel:
                continue
            chave = (de, para, rel)
            if chave in existentes:
                if origem not in existentes[chave]["origens"]:
                    existentes[chave]["origens"].append(origem)
            else:
                a = {"de": de, "para": para, "relacao": rel, "origens": [origem]}
                self.g["arestas"].append(a)
                existentes[chave] = a

    def salvar(self):
        GRAFO_JSON.write_text(json.dumps(self.g, ensure_ascii=False, indent=1), encoding="utf-8")
        np.savez_compressed(GRAFO_NPZ, vetores=self.V.astype("float32"))


def textos_de(fonte, base, filtro):
    if fonte == "resumos":
        if not CATALOGO.exists():
            raise SystemExit("Sem catalogo.json. Rode descrever.py antes.")
        for d in json.loads(CATALOGO.read_text(encoding="utf-8")):
            if filtro and filtro not in d["arquivo"].lower():
                continue
            if d.get("resumo"):
                yield d["resumo"], {"arquivo": d["arquivo"], "pagina": None}
    elif fonte == "trechos":
        _, pedacos = carregar_base(base)
        for p in pedacos:
            if filtro and filtro not in p["arquivo"].lower():
                continue
            yield p["texto"], {"arquivo": p["arquivo"], "pagina": p["pagina"]}
    else:
        raise SystemExit("Fonte: resumos | trechos <base>")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args and "--refundir" not in sys.argv:
        raise SystemExit(__doc__)
    if not API_KEY and "--refundir" not in sys.argv:
        raise SystemExit("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")
    fonte = args[0] if args else None
    base = args[1] if len(args) > 1 else None
    filtro = sys.argv[sys.argv.index("--so") + 1].lower() if "--so" in sys.argv else None

    cache = json.loads(EXTRACOES.read_text(encoding="utf-8")) if EXTRACOES.exists() else {}

    if "--refundir" in sys.argv:
        grafo = Grafo(vazio(), None)
        for chave, item in cache.items():
            grafo.incorporar(item["entidades"], item["relacoes"], item["origem"])
        grafo.salvar()
        print(f"refundido do cache: {len(cache)} textos -> "
              f"{len(grafo.g['nos'])} nós, {len(grafo.g['arestas'])} arestas")
        return

    if "--zerar" in sys.argv or not GRAFO_JSON.exists():
        grafo = Grafo(vazio(), None)
    else:
        grafo = Grafo(json.loads(GRAFO_JSON.read_text(encoding="utf-8")),
                      np.load(GRAFO_NPZ)["vetores"])
    feitos_antes = {json.dumps(o, sort_keys=True)
                    for no in grafo.g["nos"].values() for o in no["origens"]}

    cliente = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    n, falhas = 0, 0
    for texto, origem in textos_de(fonte, base, filtro):
        chave = json.dumps(origem, sort_keys=True)
        if chave in feitos_antes:
            continue
        try:
            if chave in cache:
                ents, rels = cache[chave]["entidades"], cache[chave]["relacoes"]
            else:
                ents, rels = extrair(cliente, texto)
                cache[chave] = {"origem": origem, "entidades": ents, "relacoes": rels}
            grafo.incorporar(ents, rels, origem)
            n += 1
            rot = origem["arquivo"][:44] + (f" p.{origem['pagina']}" if origem["pagina"] else "")
            print(f"  {rot}: {len(ents)} ent, {len(rels)} rel | grafo: "
                  f"{len(grafo.g['nos'])} nós, {len(grafo.g['arestas'])} arestas")
        except Exception as e:
            falhas += 1
            print(f"  FALHOU {origem['arquivo'][:44]}: {str(e)[:100]}")
        if n % 20 == 0:
            grafo.salvar()
            EXTRACOES.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    grafo.salvar()
    EXTRACOES.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"\n{n} textos extraídos ({falhas} falhas) -> {GRAFO_JSON}: "
          f"{len(grafo.g['nos'])} nós, {len(grafo.g['arestas'])} arestas")


if __name__ == "__main__":
    main()
