
import sys, json, time, pathlib
from comum import carregar_modelo, vetorizar_documentos, MODELO

QUANTOS = int(sys.argv[1]) if len(sys.argv) > 1 else 150

base = pathlib.Path("base_artigos.json")
if base.exists():
    pedacos = json.loads(base.read_text(encoding="utf-8"))
    textos = [p["texto"] for p in pedacos[:QUANTOS]]
    origem = f"{len(textos)} pedaços reais de base_artigos.json"
else:
    modelo_txt = (
        "The gyroscope measures angular rate about each body axis. Integrating this "
        "signal yields orientation, but any residual bias accumulates linearly in the "
        "estimated angle. The accelerometer at rest measures only the gravity vector, "
        "providing an absolute inclination reference that does not accumulate error "
        "because each sample is independent of all previous samples. A one-degree "
        "orientation error leaks 0.171 m/s^2 into the motion acceleration estimate. "
    )
    textos = [(modelo_txt * 3)[:900] for _ in range(QUANTOS)]
    origem = f"{QUANTOS} pedaços sintéticos (indexe primeiro para medir com texto real)"

print(f"modelo : {MODELO}")
print(f"amostra: {origem}\n")

t0 = time.perf_counter()
m = carregar_modelo()
t_carga = time.perf_counter() - t0
print(f"carregar o modelo ....... {t_carga:6.1f} s  (custo fixo, uma vez por processo)")

vetorizar_documentos(textos[:5])

t0 = time.perf_counter()
V = vetorizar_documentos(textos)
t_vet = time.perf_counter() - t0

por_pedaco = t_vet / len(textos)
print(f"vetorizar {len(textos):4d} pedaços .. {t_vet:6.1f} s")
print(f"por pedaço .............. {por_pedaco*1000:6.1f} ms")
print(f"formato da matriz ....... {V.shape}\n")

print("PROJEÇÃO (só a vetorização, sem leitura de PDF):")
for n, desc in [(1_500, "30 artigos"), (13_000, "~10 livros"), (27_000, "~20 livros")]:
    seg = n * por_pedaco;
    h, m_ = divmod(int(seg), 3600); m_ //= 60;
    print(f"  {desc:12} {n:>7,} pedaços -> {h}h{m_:02d}min");
print("\nRegra: se ~20 livros der menos de 1h, esqueça trocar de backend.")
