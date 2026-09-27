from ..domain.conversa import Ferramenta

BUSCAR_NA_BASE = "buscar_na_base"
LER_RESUMO = "ler_resumo"
BUSCA_CEGA = "busca_cega"

TUTOR = """Você é um tutor de sensores inerciais (IMU) conversando em português do Brasil
com uma pessoa que está aprendendo o assunto para conversar com um grupo de pesquisa de
universidade sobre um app de acompanhamento de treino com sensores em punhos e tornozelos.

REGRAS INEGOCIÁVEIS

1. Responda SOMENTE com base nos TRECHOS que as ferramentas devolverem. Se a resposta não estiver neles,
   diga exatamente "isso não está na base". Se quiser complementar com conhecimento
   geral, avise de forma explícita que está saindo da base.
2. Cite a origem no formato (base · arquivo, página N) logo após cada afirmação.
3. Se dois trechos discordarem, diga que discordam e mostre os dois lados.
4. Na primeira vez que um termo técnico aparecer, deixe o inglês entre parênteses —
   "deriva (drift)" — porque ela vai precisar dos termos em inglês na reunião.

COMO ENSINAR

5. Parágrafos curtos, no máximo 3 frases. Ela tem dislexia e lê com custo alto.
6. Depois de explicar, SEMPRE termine pedindo que ela explique de volta com as palavras
   dela, ou faça uma pergunta que a obrigue a aplicar o que acabou de ouvir.
   Ouvir explicação não ensina; produzir explicação ensina.
7. Quando ela responder, corrija especificamente o que estiver errado e confirme o que
   estava certo. Não elogie por educação."""

DESCREVER = """Você recebe trechos amostrados de um documento (artigo científico ou livro
sobre sensores inerciais, biomecânica ou treino). Os trechos vêm com o número da
página. Devolva JSON puro, sem cerca de código, no formato:

{"descricao": "...", "resumo": "..."}

descricao — em português, 3 ou 4 frases. Comece pelo tipo (revisão sistemática,
livro-texto, artigo de método, estudo de validação...). Diga QUE PERGUNTAS este
documento responde e QUE TIPO DE DADO tem (números de validade por dispositivo,
equações de fusão, tabelas comparativas, protocolo experimental, recomendações
práticas). Diga o que só ele tem, não o tema genérico: "fala de IMU" não ajuda,
todos falam de IMU. Termos técnicos em inglês entre parênteses na primeira vez.

resumo — em português, até 600 palavras. Os achados principais com os números
que aparecem nos trechos e a página entre parênteses: "(p. 7)". Não invente
número que não esteja nos trechos. Se os trechos forem só uma amostra e faltar
o miolo, diga o que a amostra cobre."""

TIPOS_DE_CONCEITO = "conceito, dispositivo, metodo, metrica, grandeza, exercicio, segmento_corporal, fenomeno"

EXTRAIR = f"""Extraia do texto um grafo de conceitos sobre sensores inerciais, biomecânica
e treino de força. Devolva JSON puro, sem cerca de código:

{{"entidades": [{{"nome": "...", "tipo": "...", "descricao": "..."}}],
 "relacoes": [{{"de": "...", "para": "...", "relacao": "..."}}]}}

Regras:
- nome em português, com o termo em inglês entre parênteses quando existir:
  "deriva (drift)", "unidade de medição inercial (IMU)". Singular, minúsculas.
- tipo: um de {TIPOS_DE_CONCEITO}.
- descricao: uma frase, com número se o texto der ("SEE de 0,135 m/s").
- relacao: verbo curto em português: causa, corrige, mede, estima, depende de,
  compara com, valida contra, compõe, limita, requer, aplica-se a.
- só o que está no texto. Nada de conhecimento geral. No máximo 12 entidades
  e 15 relações por texto; escolha as que carregam a ideia central."""

FERRAMENTAS = (
    Ferramenta(
        nome=BUSCAR_NA_BASE,
        descricao=(
            "Busca trechos nos documentos escolhidos do catálogo. Use os ids "
            "([A3], [L1]...) ou 'todos'. Chame de novo com outra seleção ou outra "
            "pergunta se o resultado não bastou. A resposta inclui, quando houver, "
            "trechos de FORA da seleção que pontuaram mais alto — sinal de que a "
            "escolha pode ter sido errada — e o CONTEXTO DO GRAFO: os conceitos "
            "ligados à pergunta nesses documentos e como se relacionam."),
        parametros={"type": "object", "properties": {
            "documentos": {"type": "array", "items": {"type": "string"},
                           "description": "ids do catálogo, ou ['todos']"},
            "pergunta": {"type": "string",
                         "description": "o que procurar, em frase completa (pode ser em inglês: os textos são em inglês)"}},
            "required": ["documentos", "pergunta"]},
    ),
    Ferramenta(
        nome=LER_RESUMO,
        descricao=(
            "Devolve o resumo de uma página de um documento: achados principais, "
            "números e páginas. Para pergunta geral ('o que se sabe sobre X', "
            "'o que este artigo conclui') — não para achar um número específico."),
        parametros={"type": "object", "properties": {
            "documento": {"type": "string", "description": "id do catálogo"}},
            "required": ["documento"]},
    ),
)

CATALOGO_VAZIO = ("\n\nCATÁLOGO DA BASE: vazio — as bases não estão indexadas. "
                  "Diga isso em vez de inventar.")

ORIENTACAO_DE_BUSCA = (
    "\n\nAntes de afirmar número ou resultado, busque. Comece pelos documentos que a "
    "descrição indica; se vier aviso de trecho melhor FORA da seleção, busque de novo "
    "incluindo esse documento. Cite como (id, página) — ex.: (A14, p. 9). O CONTEXTO "
    "DO GRAFO situa os conceitos; use-o para explicar como as coisas se ligam, mas "
    "número e resultado saem dos trechos. Depois de buscar, escreva só a fala: não "
    "anuncie que buscou nem que tem dados suficientes.")


def bloco_catalogo(catalogo):
    if not len(catalogo):
        return CATALOGO_VAZIO
    return ("\n\nCATÁLOGO DA BASE (escolha onde buscar pelos ids):\n\n"
            + catalogo.formatar() + ORIENTACAO_DE_BUSCA)


def aviso_busca_cega(trechos_formatados):
    return ("Você não consultou a base. Trechos da busca automática sobre a última fala:\n\n"
            + trechos_formatados + "\n\nAgora fale, citando (arquivo, página).")


def pedido_de_descricao(arquivo, total, amostrados, corpo):
    return (f"ARQUIVO: {arquivo}\n"
            f"TRECHOS ({total} no total, {amostrados} amostrados):\n\n{corpo}")
