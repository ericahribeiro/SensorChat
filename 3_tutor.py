
import sys, os
from openai import OpenAI
from tutor import responder

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
API_KEY = os.environ.get("MIMO_API_KEY", "")
COTAS = {"artigos": 4, "livros": 2}


def main():
    if not API_KEY:
        print("Faltou a chave: crie um arquivo .env com MIMO_API_KEY=...")
        sys.exit(1)

    cotas = COTAS
    if len(sys.argv) > 1:
        cotas = {sys.argv[1]: 6}

    cliente = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    historico = []
    print(f"\nTutor pronto. Buscando em: {', '.join(cotas)}. 'sair' para encerrar.\n")

    while True:
        try:
            pergunta = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        if not pergunta:
            continue

        resposta, buscas, _ = responder(cliente, historico, pergunta, cotas)
        for b in buscas:
            alvo = ", ".join(b["documentos"])
            print(f"  ({b['ferramenta']}: {alvo}" + (f" — «{b['pergunta']}»)" if b["pergunta"] else ")"))

        print(f"\ntutor > {resposta}\n")
        historico.append({"role": "user", "content": pergunta})
        historico.append({"role": "assistant", "content": resposta})


if __name__ == "__main__":
    main()