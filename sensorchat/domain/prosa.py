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

LIMIAR_CITACAO = 6.0
LIMIAR_DIGITOS = 0.14
LINHA_CURTA = 45
FRASE_CURTA = 6


def _metricas(texto):
    linhas = [linha for linha in texto.split("\n") if linha.strip()]
    tamanho = max(len(texto), 1)
    frases = [f for f in re.split(r"[.!?]\s", texto) if len(f.split()) > 1]
    return {
        "citacao": sum(peso * len(padrao.findall(texto)) for padrao, peso in CITACAO) * 1000.0 / tamanho,
        "digitos": sum(c.isdigit() for c in texto) / tamanho,
        "linha_media": statistics.mean(len(linha) for linha in linhas) if linhas else 0,
        "frase_media": statistics.mean(len(f.split()) for f in frases) if frases else 0,
        "pontinhos": len(PONTINHOS.findall(texto)),
        "indice": len(ENTRADA_INDICE.findall(texto)),
        "linhas": len(linhas),
    }


def classificar(texto):
    m = _metricas(texto)
    if m["pontinhos"] >= 2:
        return "sumário"
    if m["indice"] >= 3 and m["linha_media"] < 60:
        return "índice"
    if m["citacao"] >= LIMIAR_CITACAO:
        return "referências"
    if m["digitos"] >= LIMIAR_DIGITOS:
        return "tabela/números"
    if m["linha_media"] < LINHA_CURTA and m["frase_media"] < FRASE_CURTA and m["linhas"] >= 4:
        return "fragmento"
    return None
