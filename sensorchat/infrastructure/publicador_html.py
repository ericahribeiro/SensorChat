import html
from pathlib import Path

ESTILO = """
 body{font:16px/1.7 -apple-system,system-ui,sans-serif;max-width:820px;margin:0 auto;
 padding:32px 20px 80px;background:#f4f5f7;color:#1e2228}
 h1{font-size:1.7rem;margin:0 0 4px} h2{font-size:1.1rem;margin:32px 0 10px}
 .meta{color:#6a737d;font-size:.85rem;margin-bottom:28px}
 .plano{background:#fff;border:1px solid #dfe3e8;border-radius:4px;padding:18px 22px}
 ul{margin:6px 0 16px;padding-left:20px} li{margin:3px 0} .v{color:#8b949e;list-style:none;margin-left:-20px}
 .l{background:#fff;border:1px solid #dfe3e8;border-left:3px solid #c8ced6;
 border-radius:0 4px 4px 0;padding:12px 16px;margin:8px 0}
 .l.agente{border-left-color:#4a3ea8;background:#fbfbfe}
 .l b{font-size:.9rem} .l time{color:#8b949e;font-size:.78rem;margin-left:8px}
 .l p{margin:6px 0 0;white-space:pre-wrap} .l small{display:block;margin-top:6px;color:#8b949e;font-size:.76rem}
 @media(prefers-color-scheme:dark){body{background:#15171b;color:#e6e9ee}
 .plano,.l{background:#1d2026;border-color:#2e333b} .l.agente{background:#1f1f2b}}
"""


def _lista(itens):
    return "".join(f"<li>{html.escape(i)}</li>" for i in itens) or "<li class=v>—</li>"


def _consultas(linha):
    if not linha.consultas:
        return ""
    itens = "; ".join(
        f"{', '.join(c.documentos)} — «{c.pergunta}»" if c.pergunta else ", ".join(c.documentos)
        for c in linha.consultas)
    arquivos = "\n".join(a for c in linha.consultas for a in c.arquivos)
    return f'<small title="{html.escape(arquivos)}">consultou: {html.escape(itens)}</small>'


def _linha(linha):
    return (f'<div class="l {linha.papel}"><b>{html.escape(linha.autor)}</b>'
            f'<time>{html.escape(linha.quando[11:16])}</time><p>{html.escape(linha.texto)}</p>'
            f'{_consultas(linha)}</div>')


def renderizar(ata, momento):
    return f"""<!doctype html><meta charset=utf-8>
<title>Banca — ata e plano</title>
<style>{ESTILO}</style>
<h1>Banca — ata e plano</h1>
<div class=meta>Gerado em {momento:%d/%m/%Y às %H:%M} · {len(ata.linhas)} falas</div>
<div class=plano>
 <h2 style="margin-top:0">Decisões</h2><ul>{_lista(ata.plano.decisoes)}</ul>
 <h2>Em aberto</h2><ul>{_lista(ata.plano.abertas)}</ul>
 <h2>Riscos</h2><ul>{_lista(ata.plano.riscos)}</ul>
</div>
<h2>Ata</h2>{"".join(_linha(l) for l in ata.linhas)}"""


class PublicadorHtml:
    def __init__(self, pasta):
        self._pasta = Path(pasta)

    def publicar(self, ata, momento):
        self._pasta.mkdir(parents=True, exist_ok=True)
        destino = self._pasta / "index.html"
        destino.write_text(renderizar(ata, momento), encoding="utf-8")
        return str(destino.resolve())
