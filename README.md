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
uvicorn servidor:app --reload
```

- `http://localhost:8000/` — Banca
- `http://localhost:8000/tutor` — Tutor

### Terminal

```bash
python 3_tutor.py              # tutor buscando em artigos e livros
python 3_tutor.py artigos      # só em uma base
python 2_buscar.py artigos "deriva do giroscópio"   # busca vetorial pura, sem modelo de linguagem
```

## Adicionando documentos

Os PDFs não vão para o repositório. Para incluir documentos novos:

1. Coloque os PDFs em `pdfs_artigos/` ou `pdfs_livros/`.
2. Reindexe a base:
   ```bash
   python 1_indexar.py artigos
   ```
3. Atualize o catálogo com a descrição dos documentos novos:
   ```bash
   python descrever.py
   ```
4. Atualize o grafo de conceitos com `extrair.py` (as respostas do modelo ficam em cache
   em `extracoes.json`).

## Estrutura

| Arquivo | Função |
|---|---|
| `1_indexar.py` | Lê os PDFs de uma base, divide em pedaços e gera `base_<nome>.npz` / `.json` |
| `2_buscar.py` | Busca vetorial pelo terminal |
| `3_tutor.py` | Tutor pelo terminal |
| `servidor.py` | Servidor FastAPI com a Banca e o Tutor |
| `tutor.py` | Instruções e lógica do tutor |
| `agentes.py` | Papéis e restrições dos agentes da Banca |
| `roteador.py` | Ferramentas do agente: escolher documentos, buscar trechos, ler resumos |
| `busca_multi.py` | Busca em várias bases e catálogo de documentos |
| `grafo.py` | Consulta ao grafo de conceitos |
| `descrever.py` | Gera descrição e resumo de cada documento (`catalogo.json`) |
| `extrair.py` | Extrai conceitos e relações para o grafo |
| `comum.py` | Modelo de embeddings, leitura e gravação das bases |
| `limpeza.py`, `prosa.py` | Limpeza do texto dos PDFs e detecção de trechos de referências |
| `medir.py` | Mede a velocidade de vetorização na máquina |
| `teste_local.py` | Teste do servidor sem chave de API nem bases |

| Dado | Conteúdo |
|---|---|
| `base_*.npz` | Vetores (embeddings) de cada pedaço |
| `base_*.json` | Texto, arquivo e página de cada pedaço |
| `catalogo.json` | Descrição e resumo de cada documento |
| `grafo.json` / `grafo.npz` | Conceitos, relações e seus vetores |
| `extracoes.json` | Cache das extrações feitas pelo modelo |
| `ata.json` | Ata da Banca (gerada em uso, fora do repositório) |

## Testes

```bash
python teste_local.py
```
