FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/modelos \
    SENSORCHAT_RAIZ=/dados

WORKDIR /app

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY sensorchat sensorchat
COPY base_*.json base_*.npz catalogo.json extracoes.json grafo.json grafo.npz ./

CMD ["sh", "-c", "mkdir -p /dados \
    && cp base_*.json base_*.npz catalogo.json extracoes.json grafo.json grafo.npz /dados/ \
    && exec uvicorn sensorchat.interfaces.web.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
