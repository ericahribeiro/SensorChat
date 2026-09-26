import re
import statistics

CITACAO = [

    (re.compile(r"\b(19|20)\d{2}[a-z]?\.\s+[A-Z]"), 2.5),

    (re.compile(r"\b\d{1,3}\(\d{1,3}\),\s*\d"), 2.5),

    (re.compile(r"\b\d{2,4}\s*[–—]\s*\d{2,4}\b"), 1.5),

    (re.compile(r"\b(19|20)\d{2}[a-z]?\b"), 0.3),


    (re.compile(r"\bpp?\.\s*\d"), 1.5),
    (re.compile(r"\bvol\.", re.I), 1.5),
    (re.compile(r"\bno\.\s*\d", re.I), 1.2),
    (re.compile(r"et\s+al\.", re.I), 1.2),
    (re.compile(r"\bdoi\b|https?://|PubMed|PMID|PMCID", re.I), 1.5),
    (re.compile(r"\[\d{1,3}\]"), 0.4),
    (re.compile(r"\b[A-Z]\.\s*[A-Z]\.|\b[A-Z]\.\s+[A-Z][a-z]"), 0.8),
    (re.compile(r"[“\"][^”\"]{10,}?,[”\"]"), 1.5),
    (re.compile(r"\bProc\.|\bProceedings\b|\bConference on\b|\bJ\.\s[A-Z]"), 1.2),
]

PONTINHOS = re.compile(r"\.{4,}|\. \. \. \.")
ENTRADA_INDICE = re.compile(r"[A-Za-zÀ-ÿ],\s*\d+(\s*[,–-]\s*\d+)*\s*$", re.M)

LIMIARES = {
    "citacao": 6.0,
    "digitos": 0.14,
    "linha_curta": 45,
    "frase_curta": 6,
}


def _metricas(texto):
    linhas = [l for l in texto.split("\n") if l.strip()]
    n = max(len(texto), 1)
    frases = [f for f in re.split(r"[.!?]\s", texto) if len(f.split()) > 1]
    return {
        "citacao": sum(p * len(r.findall(texto)) for r, p in CITACAO) * 1000.0 / n,
        "digitos": sum(c.isdigit() for c in texto) / n,
        "linha_media": statistics.mean(len(l) for l in linhas) if linhas else 0,
        "frase_media": statistics.mean(len(f.split()) for f in frases) if frases else 0,
        "pontinhos": len(PONTINHOS.findall(texto)),
        "indice": len(ENTRADA_INDICE.findall(texto)),
        "linhas": len(linhas),
    }


def classificar(texto, devolver_metricas=False):
    m = _metricas(texto)
    motivo = None

    if m["pontinhos"] >= 2:
        motivo = "sumário"
    elif m["indice"] >= 3 and m["linha_media"] < 60:
        motivo = "índice"
    elif m["citacao"] >= LIMIARES["citacao"]:
        motivo = "referências"
    elif m["digitos"] >= LIMIARES["digitos"]:
        motivo = "tabela/números"
    elif (m["linha_media"] < LIMIARES["linha_curta"]
          and m["frase_media"] < LIMIARES["frase_curta"]
          and m["linhas"] >= 4):
        motivo = "fragmento"

    return (motivo, m) if devolver_metricas else motivo


def e_prosa(texto):
    return classificar(texto) is None