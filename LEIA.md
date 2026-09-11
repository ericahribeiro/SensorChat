# Banca — dois humanos, dois agentes

Reunião de trabalho onde você e o Ricardo conversam com um especialista em sensores
(ancorado nos artigos) e um arquiteto de software (ancorado nas restrições do projeto).
Os humanos falam à vontade; os agentes só falam quando chamados.

## Arquivos

| arquivo | o que é |
|---|---|
| `agentes.py` | Os dois agentes: papel, critério de sucesso, modelo. **Comece editando as RESTRIÇÕES aqui.** |
| `servidor.py` | FastAPI. Estado em `ata.json`, escrita atômica. |
| `banca.html` | A página. Sem framework, sem build. |
| `comum.py` | Busca na base RAG (o mesmo do tutor). |
| `teste_local.py` | Roda a aplicação inteira com o modelo dublado — **sem gastar crédito nenhum**. |

## Primeira vez

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn openai numpy pymupdf sentence-transformers

# 1. confira que a plumbing funciona, sem gastar nada:
python teste_local.py

# 2. as chaves (a Xiaomi fala o formato da OpenAI)
export MIMO_API_KEY="..."
export MIMO_BASE_URL="https://api.xiaomimimo.com/v1"   # ou o endpoint do Token Plan

# 3. suba
uvicorn servidor:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000 — o modelo de embedding carrega na primeira busca
(uns segundos, uma vez só, porque fica na memória).

A base de artigos precisa existir: `python 1_indexar.py artigos` na pasta do tutor,
com o `base_artigos.npz` visível daqui. Sem ela o especialista avisa que não tem base
em vez de inventar.

## Para o Ricardo entrar

```bash
# impede o Mac de dormir enquanto a sessão roda
caffeinate -dims &

# túnel: atravessa CGNAT, sem abrir porta no roteador
brew install cloudflared
cloudflared tunnel --url http://127.0.0.1:8000
```

O comando imprime um endereço `trycloudflare.com`. Ele **muda a cada execução** —
serve para sessão marcada. Para endereço fixo, é preciso um túnel nomeado com domínio.

**Ponha o Cloudflare Access na frente antes de mandar o link.** Sem isso, quem
descobrir o endereço gasta os seus créditos. Cadastre o e-mail dele; ele recebe um
código e entra.

Tampa aberta e cabo na tomada enquanto a sessão roda.

## Botões

- **Chamar a banca** — os dois agentes falam, nessa ordem.
- **Só sensores / Só arquiteto** — quando você quer um parecer específico.
- **Fechar tópico** — o secretário lê a ata e atualiza decisões, pontos abertos e riscos.
- **Publicar** — gera `publico/index.html` com a ata e o plano. Suba isso em qualquer
  hospedagem estática grátis: ele lê quando quiser, sem depender do seu notebook estar ligado.

## O que fazer quando ficar ruim

**Os agentes concordam com tudo.** É o modo de falha principal. Não conserte pedindo
mais desacordo no prompt — isso dá discordância decorativa. Aperte mais os critérios
de sucesso em `agentes.py`, que são incompatíveis por construção: o arquiteto falha se
não entregar no prazo, o especialista falha se a medição não sobreviver a um revisor.

**O especialista cita coisa que não está no artigo.** Diminua `TRECHOS_POR_TURNO` de
6 para 3. Contexto irrelevante em excesso piora, não melhora.

**As falas ficam longas e cerimoniosas.** Baixe `max_completion_tokens` de 700 para 400.
Limite curto força objeção em vez de ensaio.

**A conversa não sai do lugar.** Aperte "fechar tópico". Se o plano não mudou depois de
dez falas, a reunião estava girando — e agora vocês veem isso.
