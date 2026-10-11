from pathlib import Path


class RepositorioAudioEmArquivo:
    def __init__(self, pasta, extensao="mp3"):
        self._pasta = Path(pasta)
        self._extensao = extensao

    def ler(self, chave):
        caminho = self._caminho(chave)
        return caminho.read_bytes() if caminho.exists() else None

    def gravar(self, chave, dados):
        self._pasta.mkdir(parents=True, exist_ok=True)
        temporario = self._caminho(chave).with_suffix(".tmp")
        temporario.write_bytes(dados)
        temporario.replace(self._caminho(chave))

    def _caminho(self, chave):
        return self._pasta / f"{chave}.{self._extensao}"
