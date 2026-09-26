import sys
from comum import carregar_base, buscar

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Uso: python 2_buscar.py <base> "sua pergunta"')
        sys.exit(1)
    base = sys.argv[1]
    pergunta = " ".join(sys.argv[2:])

    V, pedacos = carregar_base(base)
    for nota, p in buscar(pergunta, V, pedacos):
        print(f"\n{'='*70}\n[{nota:.3f}] {p['arquivo']} — página {p['pagina']}\n{'='*70}")
        print(p["texto"][:700])
