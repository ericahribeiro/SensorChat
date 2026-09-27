from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoBusca:
    dentro: list
    fora: list
    nao_encontrados: tuple


def _por_nota(trechos):
    return sorted(trechos, key=lambda t: -t.nota)


def combinar_por_cotas(candidatos, cotas, total):
    escolhidos, usados = [], {}
    for nome, trechos in candidatos.items():
        garantidos = trechos[:cotas.get(nome, 0)]
        escolhidos.extend(garantidos)
        usados[nome] = len(garantidos)
    sobra = _por_nota(t for nome, trechos in candidatos.items() for t in trechos[usados[nome]:])
    escolhidos.extend(sobra[:max(0, total - len(escolhidos))])
    return _por_nota(escolhidos)[:total]


def buscar_na_selecao(bases, vetor, arquivos, total, fora):
    dentro, restante = [], []
    for base in bases:
        da_selecao, de_fora = base.melhores_por_selecao(vetor, arquivos, total)
        dentro.extend(da_selecao)
        restante.extend(de_fora)
    dentro = _por_nota(dentro)[:total]
    piso = dentro[0].nota if dentro else -1.0
    restante = _por_nota(t for t in restante if t.nota > piso)[:fora]
    return dentro, restante
