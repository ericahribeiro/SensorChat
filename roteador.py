"""
Roteamento: o agente escolhe ONDE buscar antes de buscar.

Em vez de a busca vetorial rodar às cegas sobre a última fala, o agente
recebe o catálogo (id, base, arquivo, descrição de cada documento) e duas
ferramentas:

  buscar_na_base(documentos, pergunta) — trechos dentro dos documentos escolhidos
                                         + o pedaço do grafo de conceitos que toca a
                                         pergunta nesses documentos (grafo.py)
  ler_resumo(documento)                — o resumo de uma página, para pergunta geral

A busca no grafo vai junto com a vetorial, na mesma chamada: o agente escolhe
os documentos uma vez e recebe evidência (trechos com página) e contexto (o que
se liga a quê). Para quem está começando, o segundo é o que situa o primeiro.

Ele pode chamar quantas vezes precisar (até MAX_RODADAS), e só então fala.

Três redes de segurança, porque escolha errada não pode ser irrecuperável:
  1. a busca devolve também o que ficou FORA da seleção e pontuou acima do
     melhor de dentro — o agente vê o que perdeu;
  2. "todos" é uma seleção válida;
  3. se o agente não buscar nada e o chamador exigir busca, roda-se a busca
     cega da fala mais recente e o modelo fala de novo com ela na mão.
"""
import json
from busca_multi import (buscar_em, buscar_varias, catalogo,
                         formatar_catalogo, formatar_trechos, resolver)
import grafo

MAX_RODADAS = 4          # chamadas de ferramenta antes de forçar a fala
TRECHOS = 6

FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "buscar_na_base",
        "description": (
            "Busca trechos nos documentos escolhidos do catálogo. Use os ids "
            "([A3], [L1]...) ou 'todos'. Chame de novo com outra seleção ou outra "
            "pergunta se o resultado não bastou. A resposta inclui, quando houver, "
            "trechos de FORA da seleção que pontuaram mais alto — sinal de que a "
            "escolha pode ter sido errada — e o CONTEXTO DO GRAFO: os conceitos "
            "ligados à pergunta nesses documentos e como se relacionam."),
        "parameters": {"type": "object", "properties": {
            "documentos": {"type": "array", "items": {"type": "string"},
                           "description": "ids do catálogo, ou ['todos']"},
            "pergunta": {"type": "string",
                         "description": "o que procurar, em frase completa (pode ser em inglês: os textos são em inglês)"}},
            "required": ["documentos", "pergunta"]}}},
    {"type": "function", "function": {
        "name": "ler_resumo",
        "description": (
            "Devolve o resumo de uma página de um documento: achados principais, "
            "números e páginas. Para pergunta geral ('o que se sabe sobre X', "
            "'o que este artigo conclui') — não para achar um número específico."),
        "parameters": {"type": "object", "properties": {
            "documento": {"type": "string", "description": "id do catálogo"}},
            "required": ["documento"]}}},
]


def executar(nome, args, total=TRECHOS):
    """Roda uma ferramenta. Devolve (texto para o modelo, ids dos conceitos do grafo tocados)."""
    if nome == "buscar_na_base":
        docs = args.get("documentos") or ["todos"]
        dentro, fora, perdidos = buscar_em(args.get("pergunta", ""), docs, total)
        partes = []
        if perdidos:
            partes.append("Não reconheci: " + ", ".join(perdidos) + ". Use os ids do catálogo.")
        partes.append(("TRECHOS DA SELEÇÃO:\n\n" + formatar_trechos(dentro)) if dentro
                      else "Nada encontrado na seleção.")
        if fora:
            partes.append("FORA DA SELEÇÃO, com nota maior que o melhor de dentro:\n\n"
                          + formatar_trechos(fora))
        bloco, conceitos = contexto_grafo(args.get("pergunta", ""), docs)
        partes.append(bloco)
        return "\n\n".join(p for p in partes if p), conceitos

    if nome == "ler_resumo":
        it = resolver(args.get("documento", ""))
        if not it:
            return "Documento não reconhecido. Use os ids do catálogo.", []
        if not it["resumo"]:
            return f"[{it['id']}] ainda não tem resumo (rode descrever.py). Use buscar_na_base.", []
        return f"RESUMO DE [{it['id']}] {it['arquivo']}:\n\n{it['resumo']}", []

    return f"Ferramenta desconhecida: {nome}", []


def contexto_grafo(pergunta, docs):
    """O pedaço do grafo que toca a pergunta, restrito aos documentos escolhidos.
    Devolve (texto, ids dos conceitos centrais)."""
    itens = catalogo()
    arquivos = None
    if docs and not any(d.strip().lower() == "todos" for d in docs):
        arquivos = [it["arquivo"] for d in docs for it in [resolver(d, itens)] if it]
    centrais, arestas = grafo.consultar(pergunta, arquivos)
    return grafo.formatar(centrais, arestas, {it["arquivo"]: it["id"] for it in itens}), centrais


def _msg_assistente(m):
    """A mensagem do modelo com as chamadas, no formato que a API aceita de volta."""
    return {"role": "assistant", "content": m.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name,
                                         "arguments": c.function.arguments}}
                           for c in m.tool_calls]}


def responder_com_busca(cliente, modelo, mensagens, max_tokens, extra_body=None,
                        busca_cega=None, cotas=None, max_rodadas=MAX_RODADAS):
    """
    Conversa com ferramentas até o modelo falar. Devolve (resposta, buscas), onde
    resposta é o objeto da última chamada e buscas é a lista do que ele consultou:
    [{"ferramenta": ..., "documentos": [...], "pergunta": ...}].

    busca_cega: texto para a busca automática caso o modelo não busque nada.
                None desliga a rede de segurança.
    """
    mensagens = list(mensagens)
    buscas = []
    extra = extra_body or {}

    for _ in range(max_rodadas):
        r = cliente.chat.completions.create(
            model=modelo, messages=mensagens, tools=FERRAMENTAS,
            max_completion_tokens=max_tokens, extra_body=extra)
        m = r.choices[0].message
        if not m.tool_calls:
            break
        mensagens.append(_msg_assistente(m))
        for c in m.tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            docs = (args.get("documentos") or
                    ([args["documento"]] if args.get("documento") else []))
            # guarda o id como o modelo escreveu e o arquivo que ele resolveu:
            # quem lê a ata vê "A14" e precisa saber que artigo é esse
            texto, conceitos = executar(c.function.name, args)
            buscas.append({"ferramenta": c.function.name,
                           "documentos": docs,
                           "arquivos": [(resolver(d) or {}).get("arquivo", d) for d in docs],
                           "pergunta": args.get("pergunta", ""),
                           "conceitos": conceitos})      # nós do grafo que a busca tocou
            mensagens.append({"role": "tool", "tool_call_id": c.id, "content": texto})
    else:
        # estourou as rodadas: fala agora, sem ferramenta
        r = cliente.chat.completions.create(
            model=modelo, messages=mensagens,
            max_completion_tokens=max_tokens, extra_body=extra)

    if not buscas and busca_cega:
        try:
            achados = buscar_varias(busca_cega, cotas, TRECHOS, silencioso=True)
        except SystemExit:
            achados = []
        if achados:
            buscas.append({"ferramenta": "busca_cega", "documentos": ["todos"],
                           "arquivos": ["todos"], "pergunta": busca_cega})
            mensagens.append({"role": "user", "content":
                "Você não consultou a base. Trechos da busca automática sobre a última fala:\n\n"
                + formatar_trechos(achados) + "\n\nAgora fale, citando (arquivo, página)."})
            r = cliente.chat.completions.create(
                model=modelo, messages=mensagens,
                max_completion_tokens=max_tokens, extra_body=extra)

    return r, buscas


def bloco_catalogo():
    """Texto do catálogo para colar no prompt de sistema."""
    itens = catalogo()
    if not itens:
        return "\n\nCATÁLOGO DA BASE: vazio — as bases não estão indexadas. Diga isso em vez de inventar."
    return ("\n\nCATÁLOGO DA BASE (escolha onde buscar pelos ids):\n\n" + formatar_catalogo(itens)
            + "\n\nAntes de afirmar número ou resultado, busque. Comece pelos documentos que a "
              "descrição indica; se vier aviso de trecho melhor FORA da seleção, busque de novo "
              "incluindo esse documento. Cite como (id, página) — ex.: (A14, p. 9). O CONTEXTO "
              "DO GRAFO situa os conceitos; use-o para explicar como as coisas se ligam, mas "
              "número e resultado saem dos trechos. Depois de buscar, escreva só a fala: não "
              "anuncie que buscou nem que tem dados suficientes.")
