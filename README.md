# SensorChat

Assistente de estudo sobre sensores inerciais (IMU) aplicados a treino e biomecânica.
Responde perguntas com base numa coleção de artigos e livros, citando arquivo e página
de cada trecho usado.

O projeto tem duas interfaces:

- **Tutor** — conversa de perguntas e respostas sobre o conteúdo da base, com um mapa de
  conceitos ao lado.
- **Banca** — uma reunião simulada em que agentes (especialista em sensores, engenheiro
  embarcado, arquiteto de software) discutem o projeto do piloto, consultando a mesma base.
  A conversa vira uma ata, que pode ser resumida num plano e publicada como HTML.

## Como funciona

1. **Indexação** — o texto dos PDFs é extraído, limpo (cabeçalhos, rodapés e referências
   saem) e dividido em pedaços. Cada pedaço vira um vetor com o modelo
   `intfloat/multilingual-e5-base`.
2. **Catálogo e grafo** — um modelo de linguagem descreve cada documento (`catalogo.json`)
   e extrai conceitos e relações entre eles (`grafo.json`).
3. **Resposta** — o agente recebe o catálogo, escolhe em quais documentos buscar, recupera
   os trechos mais parecidos com a pergunta e responde só com base neles.

## Instalação

Requer Python 3.10+.

```bash
git clone https://github.com/ericahribeiro/SensorChat.git
cd SensorChat
python -m venv .venv
source .venv/bin/activate        
pip install -r requirements.txt
```

Na primeira execução, o `sentence-transformers` baixa o modelo de embeddings (~1 GB).
O código usa GPU (CUDA ou Apple MPS) quando disponível.

### Configuração

Crie um arquivo `.env` na raiz do projeto:

```
MIMO_API_KEY=sua-chave-aqui
MIMO_BASE_URL=https://api.xiaomimimo.com/v1   # opcional, esse é o padrão
BANCA_USUARIO=banca                           # opcional
BANCA_SENHA=                                  # opcional; se preenchida, protege o servidor com login
```

O `.env` está no `.gitignore` e não deve ir para o repositório.

## Uso

As bases já indexadas (`base_*.npz` e `base_*.json`) vêm no repositório, então os PDFs
não são necessários para usar o assistente.

### Servidor web

```bash
uvicorn sensorchat.interfaces.web.main:app --reload
```

- `http://localhost:8000/` — Banca
- `http://localhost:8000/tutor` — Tutor

### Logs

O servidor e os comandos de terminal registram cada passo: pergunta recebida, vetorização,
busca, contexto do grafo, envio ao LLM e resposta (com tempo e tokens), ferramentas
chamadas e turnos da banca. O log de acesso de `/estado`, que a página da banca consulta a
cada 1,5 s, fica de fora.

O nível padrão é `INFO`. Para ver só avisos e erros:

```bash
SENSORCHAT_LOG=WARNING uvicorn sensorchat.interfaces.web.main:app
```

### Terminal

```bash
python -m sensorchat tutor                                  # tutor buscando em artigos e livros
python -m sensorchat tutor artigos                          # só em uma base
python -m sensorchat buscar artigos "deriva do giroscópio"  # busca vetorial pura, sem modelo de linguagem
python -m sensorchat --help                                 # todos os comandos
```

## Adicionando documentos

Os PDFs não vão para o repositório. Para incluir documentos novos:

1. Coloque os PDFs em `pdfs_artigos/` ou `pdfs_livros/`.
2. Reindexe a base (`--mostrar` exibe exemplos do que foi descartado):
   ```bash
   python -m sensorchat indexar artigos
   ```
3. Descreva os documentos novos no catálogo (`--tudo` refaz todos, `--so <nome>` filtra):
   ```bash
   python -m sensorchat descrever
   ```
4. Atualize o grafo de conceitos a partir dos resumos ou dos trechos de uma base:
   ```bash
   python -m sensorchat extrair resumos
   python -m sensorchat extrair trechos artigos
   python -m sensorchat extrair --refundir   # reconstrói o grafo só com o cache, sem chamar o modelo
   ```
   As respostas do modelo ficam em cache em `extracoes.json`.

## Arquitetura

O código segue arquitetura limpa com DDD: as regras de negócio não dependem de framework,
banco de dados ou API. As dependências apontam sempre para dentro.

```
interfaces  →  application  →  domain
     ↓               ↑
infrastructure ──────┘  (implementa as portas da aplicação)
```

| Camada | Pasta | Conteúdo |
|---|---|---|
| Domínio | `sensorchat/domain/` | Entidades e regras puras: pedaços, catálogo, busca por cotas, grafo de conceitos e fusão, ata, agentes da banca, limpeza e fatiamento de texto |
| Aplicação | `sensorchat/application/` | Casos de uso (tutor, banca, indexar, descrever, extrair), roteamento de busca, prompts e **portas** (interfaces) |
| Infraestrutura | `sensorchat/infrastructure/` | Adaptadores das portas: arquivos JSON/NPZ, PyMuPDF, sentence-transformers, API OpenAI, publicação HTML |
| Interfaces | `sensorchat/interfaces/` | FastAPI (`web/`) e linha de comando (`cli/`) |
| Composição | `sensorchat/container.py` | Monta os casos de uso com os adaptadores concretos |

| Dado | Conteúdo |
|---|---|
| `base_*.npz` | Vetores (embeddings) de cada pedaço |
| `base_*.json` | Texto, arquivo e página de cada pedaço |
| `catalogo.json` | Descrição e resumo de cada documento |
| `grafo.json` / `grafo.npz` | Conceitos, relações e seus vetores |
| `extracoes.json` | Cache das extrações feitas pelo modelo |
| `ata.json` | Ata da Banca (gerada em uso, fora do repositório) |

## Testes

Os testes usam um modelo de linguagem e um vetorizador falsos, então não precisam de chave
de API nem do modelo de embeddings.

```bash
python -m unittest discover -s tests -t .
```
