#Precisa da variavel de ambiente ANTHROPIC_API_KEY.
import sys, os
import anthropic
from comum import carregar_base, buscar

# Confirir a lista atual de modelos na documentação — os identificadores mudam.
MODELO_CONVERSA = "claude-sonnet-4-5"
QUANTOS_TRECHOS = 6

INSTRUCOES = """Você é um tutor de sensores inerciais (IMU) conversando em português do Brasil
com uma pessoa que está aprendendo o assunto para conversar com um grupo de pesquisa de
universidade sobre um app de acompanhamento de treino com sensores em punhos e tornozelos.

REGRAS INEGOCIÁVEIS

1. Responda SOMENTE com base nos TRECHOS fornecidos. Se a resposta não estiver neles,
   diga exatamente "isso não está nos artigos da base". Se quiser complementar com
   conhecimento geral, avise de forma explícita que está saindo da base.
2. Cite a origem no formato (arquivo, página N) logo após cada afirmação.
3. Se dois trechos discordarem, diga que discordam e mostre os dois lados. Não escolha
   um vencedor em silêncio.
4. Na primeira vez que um termo técnico aparecer, deixe o inglês entre parênteses —
   "deriva (drift)" — porque ela vai precisar dos termos em inglês na reunião.

COMO ENSINAR

5. Parágrafos curtos, no máximo 3 frases. Ela tem dislexia e lê com custo alto.
6. Depois de explicar, SEMPRE termine pedindo que ela explique de volta com as palavras
   dela, ou faça uma pergunta que a obrigue a aplicar o que acabou de ouvir.
   Este é o ponto principal: ouvir explicação não ensina; produzir explicação ensina.
7. Quando ela responder, corrija especificamente o que estiver errado e confirme o que
   estava certo. Não elogie por educação.
8. Se ela pedir só a resposta, dê a resposta — mas volte a pedir a explicação na
   pergunta seguinte."""


def main():
    if len(sys.argv) != 2:
        print("Uso: python 3_tutor.py <base>    (ex: artigos, livros)")
        sys.exit(1)
    base = sys.argv[1]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Faltou: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    V, pedacos = carregar_base(base)
    cliente = anthropic.Anthropic()
    historico = []

    print(f"\nTutor pronto sobre a base '{base}'. 'sair' para encerrar.\n")
    while True:
        try:
            pergunta = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        if not pergunta:
            continue

        achados = buscar(pergunta, V, pedacos, QUANTOS_TRECHOS)
        contexto = "\n\n---\n\n".join(
            f"[{p['arquivo']}, página {p['pagina']}]\n{p['texto']}" for _, p in achados
        )

        historico.append({
            "role": "user",
            "content": f"TRECHOS DA BASE:\n\n{contexto}\n\n---\n\nPERGUNTA: {pergunta}",
        })

        r = cliente.messages.create(
            model=MODELO_CONVERSA,
            max_tokens=1500,
            system=INSTRUCOES,
            messages=historico[-8:],
        )
        resposta = r.content[0].text
        print(f"\ntutor > {resposta}\n")
        historico.append({"role": "assistant", "content": resposta})

        # Para ouvir a resposta no Mac descomentar:
        # import subprocess; subprocess.run(["say", "-v", "Luciana", resposta])


if __name__ == "__main__":
    main()
