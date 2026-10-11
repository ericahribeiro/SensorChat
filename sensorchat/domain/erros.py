class ErroDeDominio(Exception):
    pass


class BaseInexistente(ErroDeDominio):
    def __init__(self, nome):
        super().__init__(f"Base '{nome}' não existe. Rode:  python -m sensorchat indexar {nome}")
        self.nome = nome


class NenhumaBaseDisponivel(ErroDeDominio):
    def __init__(self):
        super().__init__("Nenhuma base disponível. Rode:  python -m sensorchat indexar <base>")


class CatalogoAusente(ErroDeDominio):
    def __init__(self):
        super().__init__("Sem catálogo. Rode:  python -m sensorchat descrever")


class FalaVazia(ErroDeDominio):
    pass


class PerguntaVazia(ErroDeDominio):
    pass


class BancaOcupada(ErroDeDominio):
    def __init__(self):
        super().__init__("a banca já está falando")


class RespostaInvalida(ErroDeDominio):
    def __init__(self, bruto):
        super().__init__("o modelo não devolveu JSON")
        self.bruto = bruto


class DocumentoDesconhecido(ErroDeDominio):
    def __init__(self, referencia):
        super().__init__(f"documento '{referencia}' não está na biblioteca")


class BlocoInexistente(ErroDeDominio):
    def __init__(self, numero):
        super().__init__(f"o documento não tem o trecho {numero}")


class ArquivoInvalido(ErroDeDominio):
    pass


class ArquivoRepetido(ErroDeDominio):
    def __init__(self, nome):
        super().__init__(f"'{nome}' já está na biblioteca")


class AtualizacaoEmAndamento(ErroDeDominio):
    def __init__(self):
        super().__init__("a biblioteca já está sendo atualizada")


class VozIndisponivel(ErroDeDominio):
    pass
