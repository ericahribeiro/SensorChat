import logging

from ..application.registro import cronometrar, resumir

MODELO = "intfloat/multilingual-e5-base"
PREFIXO_DOCUMENTO = "passage: "
PREFIXO_PERGUNTA = "query: "

log = logging.getLogger(__name__)


def escolher_dispositivo():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


class VetorizadorE5:
    def __init__(self, modelo=MODELO):
        self.nome_modelo = modelo
        self._modelo = None

    def carregar(self):
        if self._modelo is None:
            from sentence_transformers import SentenceTransformer
            dispositivo = escolher_dispositivo()
            log.info("carregando modelo de embeddings %s em %s (a primeira vez baixa ~1 GB)",
                     self.nome_modelo, dispositivo)
            with cronometrar() as tempo:
                self._modelo = SentenceTransformer(self.nome_modelo, device=dispositivo)
            log.info("modelo de embeddings pronto em %.1fs", tempo.segundos)
        return self._modelo

    def vetorizar_documentos(self, textos, lote=32):
        modelo = self.carregar()
        log.info("vetorizando %d textos (lote de %d)", len(textos), lote)
        with cronometrar() as tempo:
            vetores = modelo.encode(
                [PREFIXO_DOCUMENTO + t for t in textos],
                batch_size=lote,
                normalize_embeddings=True,
                show_progress_bar=len(textos) > lote,
                convert_to_numpy=True,
            ).astype("float32")
        log.info("%d textos vetorizados em %.1fs", len(textos), tempo.segundos)
        return vetores

    def vetorizar_pergunta(self, texto):
        modelo = self.carregar()
        log.info("vetorizando a pergunta «%s»", resumir(texto))
        with cronometrar() as tempo:
            vetor = modelo.encode(
                [PREFIXO_PERGUNTA + texto],
                normalize_embeddings=True,
                convert_to_numpy=True,
            ).astype("float32")[0]
        log.info("pergunta vetorizada em %.2fs", tempo.segundos)
        return vetor
