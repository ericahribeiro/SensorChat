import argparse
import time

from ...container import Container
from ...domain.conversa import Mensagem
from ...domain.erros import ErroDeDominio
from ...infrastructure import logs
from ...infrastructure.configuracao import ChaveAusente, Configuracao
from ...infrastructure.vetorizador import MODELO as MODELO_VETORIZADOR

SAIR = {"sair", "exit", "quit"}
TEXTO_SINTETICO = (
    "The gyroscope measures angular rate about each body axis. Integrating this "
    "signal yields orientation, but any residual bias accumulates linearly in the "
    "estimated angle. The accelerometer at rest measures only the gravity vector, "
    "providing an absolute inclination reference that does not accumulate error "
    "because each sample is independent of all previous samples. A one-degree "
    "orientation error leaks 0.171 m/s^2 into the motion acceleration estimate. "
)


def indexar(container, args):
    container.indexar.executar(args.base, mostrar=args.mostrar)


def buscar(container, args):
    base = container.busca.base(args.base)
    if base is None:
        raise SystemExit(f"Base '{args.base}' não existe. Rode:  python -m sensorchat indexar {args.base}")
    vetor = container.vetorizador.vetorizar_pergunta(" ".join(args.pergunta))
    for trecho in base.melhores(vetor, 6):
        print(f"\n{'=' * 70}\n[{trecho.nota:.3f}] {trecho.pedaco.arquivo} — página {trecho.pedaco.pagina}\n{'=' * 70}")
        print(trecho.pedaco.texto[:700])


def tutor(container, args):
    container.configuracao.exigir_chave()
    cotas = {args.base: 6} if args.base else None
    alvo = ", ".join(cotas) if cotas else "artigos, livros"
    historico = []
    print(f"\nTutor pronto. Buscando em: {alvo}. 'sair' para encerrar.\n")
    while True:
        try:
            pergunta = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in SAIR:
            break
        if not pergunta:
            continue
        resultado = container.tutor.perguntar(pergunta, historico, cotas)
        for consulta in resultado.consultas:
            documentos = ", ".join(consulta.documentos)
            sufixo = f" — «{consulta.pergunta}»)" if consulta.pergunta else ")"
            print(f"  ({consulta.ferramenta}: {documentos}{sufixo}")
        print(f"\ntutor > {resultado.resposta}\n")
        historico += [Mensagem.usuario(pergunta), Mensagem.assistente(resultado.resposta)]


def descrever(container, args):
    container.configuracao.exigir_chave()
    container.descrever.executar(tudo=args.tudo, filtro=args.so)


def extrair(container, args):
    if args.refundir:
        container.extrair.refundir()
        return
    if not args.fonte or (args.fonte == "trechos" and not args.base):
        raise SystemExit("Uso: python -m sensorchat extrair resumos | trechos <base> [--so X] [--zerar]")
    container.configuracao.exigir_chave()
    container.extrair.executar(args.fonte, args.base, filtro=args.so, zerar=args.zerar)


def medir(container, args):
    base = container.busca.base("artigos")
    if base:
        textos = [p.texto for p in base.pedacos[:args.quantos]]
        origem = f"{len(textos)} pedaços reais da base de artigos"
    else:
        textos = [(TEXTO_SINTETICO * 3)[:900] for _ in range(args.quantos)]
        origem = f"{args.quantos} pedaços sintéticos (indexe primeiro para medir com texto real)"
    print(f"modelo : {MODELO_VETORIZADOR}\namostra: {origem}\n")

    inicio = time.perf_counter()
    container.vetorizador.carregar()
    print(f"carregar o modelo ....... {time.perf_counter() - inicio:6.1f} s  (custo fixo, uma vez por processo)")

    container.vetorizador.vetorizar_documentos(textos[:5])
    inicio = time.perf_counter()
    vetores = container.vetorizador.vetorizar_documentos(textos)
    duracao = time.perf_counter() - inicio

    por_pedaco = duracao / len(textos)
    print(f"vetorizar {len(textos):4d} pedaços .. {duracao:6.1f} s")
    print(f"por pedaço .............. {por_pedaco * 1000:6.1f} ms")
    print(f"formato da matriz ....... {vetores.shape}\n")
    print("PROJEÇÃO (só a vetorização, sem leitura de PDF):")
    for quantidade, descricao in [(1_500, "30 artigos"), (13_000, "~10 livros"), (27_000, "~20 livros")]:
        horas, resto = divmod(int(quantidade * por_pedaco), 3600)
        print(f"  {descricao:12} {quantidade:>7,} pedaços -> {horas}h{resto // 60:02d}min")
    print("\nRegra: se ~20 livros der menos de 1h, esqueça trocar de backend.")


def _analisador():
    analisador = argparse.ArgumentParser(prog="python -m sensorchat")
    comandos = analisador.add_subparsers(dest="comando", required=True)

    p = comandos.add_parser("indexar", help="lê os PDFs de uma base e gera os vetores")
    p.add_argument("base")
    p.add_argument("--mostrar", action="store_true")
    p.set_defaults(executar=indexar)

    p = comandos.add_parser("buscar", help="busca vetorial pura em uma base")
    p.add_argument("base")
    p.add_argument("pergunta", nargs="+")
    p.set_defaults(executar=buscar)

    p = comandos.add_parser("tutor", help="conversa com o tutor pelo terminal")
    p.add_argument("base", nargs="?")
    p.set_defaults(executar=tutor)

    p = comandos.add_parser("descrever", help="gera descrição e resumo de cada documento")
    p.add_argument("--tudo", action="store_true")
    p.add_argument("--so")
    p.set_defaults(executar=descrever)

    p = comandos.add_parser("extrair", help="extrai conceitos e relações para o grafo")
    p.add_argument("fonte", nargs="?", choices=["resumos", "trechos"])
    p.add_argument("base", nargs="?")
    p.add_argument("--so")
    p.add_argument("--zerar", action="store_true")
    p.add_argument("--refundir", action="store_true")
    p.set_defaults(executar=extrair)

    p = comandos.add_parser("medir", help="mede a velocidade de vetorização")
    p.add_argument("quantos", nargs="?", type=int, default=150)
    p.set_defaults(executar=medir)

    return analisador


def main(argv=None):
    args = _analisador().parse_args(argv)
    logs.configurar()
    container = Container(Configuracao.do_ambiente())
    try:
        args.executar(container, args)
    except (ErroDeDominio, ChaveAusente, ValueError) as erro:
        raise SystemExit(str(erro))
