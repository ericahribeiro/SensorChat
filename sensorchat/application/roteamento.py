import logging

from ..domain.conversa import Consulta, Mensagem
from ..domain.documentos import TODOS, formatar_trechos
from ..domain.erros import NenhumaBaseDisponivel
from . import instrucoes
from .registro import resumir

MAX_RODADAS = 4
TRECHOS = 6

log = logging.getLogger(__name__)


class RoteadorDeBusca:
    def __init__(self, modelo_linguagem, busca, grafo, max_rodadas=MAX_RODADAS, trechos=TRECHOS):
        self._modelo = modelo_linguagem
        self._busca = busca
        self._grafo = grafo
        self._max_rodadas = max_rodadas
        self._trechos = trechos

    def bloco_catalogo(self):
        return instrucoes.bloco_catalogo(self._busca.catalogo())

    def responder(self, modelo, mensagens, max_tokens, sem_raciocinio=False, busca_cega=None, cotas=None):
        mensagens = list(mensagens)
        consultas = []
        catalogo = self._busca.catalogo()

        for rodada in range(1, self._max_rodadas + 1):
            resposta = self._modelo.completar(modelo, mensagens, max_tokens,
                                              instrucoes.FERRAMENTAS, sem_raciocinio)
            if not resposta.chamadas:
                log.info("modelo respondeu após %d consulta(s) à base", len(consultas))
                break
            log.info("rodada %d/%d: modelo pediu %d ferramenta(s)", rodada, self._max_rodadas,
                     len(resposta.chamadas))
            mensagens.append(Mensagem.assistente(resposta.texto, resposta.chamadas))
            for chamada in resposta.chamadas:
                consulta, texto = self._atender(chamada, catalogo)
                consultas.append(consulta)
                mensagens.append(Mensagem.resultado(chamada.id, texto))
        else:
            log.warning("limite de %d rodadas de ferramentas atingido; pedindo a resposta sem ferramentas",
                        self._max_rodadas)
            resposta = self._modelo.completar(modelo, mensagens, max_tokens, (), sem_raciocinio)

        if not consultas and busca_cega:
            log.info("modelo não consultou a base; acionando a busca automática")
            achados = self._busca_automatica(busca_cega, cotas)
            if achados:
                consultas.append(Consulta(instrucoes.BUSCA_CEGA, (TODOS,), (TODOS,), busca_cega))
                mensagens.append(Mensagem.usuario(instrucoes.aviso_busca_cega(formatar_trechos(achados))))
                resposta = self._modelo.completar(modelo, mensagens, max_tokens, (), sem_raciocinio)
            else:
                log.warning("busca automática não encontrou trechos; fica a resposta sem base")

        return resposta, consultas

    def executar(self, nome, argumentos):
        if nome == instrucoes.BUSCAR_NA_BASE:
            return self._buscar_na_base(argumentos)
        if nome == instrucoes.LER_RESUMO:
            return self._ler_resumo(argumentos), []
        log.warning("modelo pediu uma ferramenta desconhecida: %s", nome)
        return f"Ferramenta desconhecida: {nome}", []

    def _atender(self, chamada, catalogo):
        argumentos = chamada.argumentos_dict()
        documentos = argumentos.get("documentos") or (
            [argumentos["documento"]] if argumentos.get("documento") else [])
        documentos = [str(d) for d in documentos]
        log.info("executando %s: documentos [%s]%s", chamada.nome, ", ".join(documentos),
                 f", pergunta «{resumir(argumentos['pergunta'])}»" if argumentos.get("pergunta") else "")
        texto, conceitos = self.executar(chamada.nome, argumentos)
        consulta = Consulta(
            ferramenta=chamada.nome,
            documentos=tuple(documentos),
            arquivos=tuple(catalogo.arquivo_de(d) for d in documentos),
            pergunta=argumentos.get("pergunta", ""),
            conceitos=tuple(conceitos),
        )
        return consulta, texto

    def _buscar_na_base(self, argumentos):
        documentos = [str(d) for d in argumentos.get("documentos") or [TODOS]]
        pergunta = argumentos.get("pergunta", "")
        try:
            resultado = self._busca.buscar_em(pergunta, documentos, self._trechos)
        except NenhumaBaseDisponivel as erro:
            log.warning("busca sem nenhuma base indexada")
            return str(erro), []

        partes = []
        if resultado.nao_encontrados:
            partes.append("Não reconheci: " + ", ".join(resultado.nao_encontrados)
                          + ". Use os ids do catálogo.")
        partes.append(("TRECHOS DA SELEÇÃO:\n\n" + formatar_trechos(resultado.dentro))
                      if resultado.dentro else "Nada encontrado na seleção.")
        if resultado.fora:
            partes.append("FORA DA SELEÇÃO, com nota maior que o melhor de dentro:\n\n"
                          + formatar_trechos(resultado.fora))
        contexto, conceitos = self._grafo.contexto(pergunta, self._busca.catalogo(), documentos)
        partes.append(contexto)
        return "\n\n".join(p for p in partes if p), conceitos

    def _ler_resumo(self, argumentos):
        item = self._busca.catalogo().resolver(str(argumentos.get("documento", "")))
        if not item:
            log.warning("resumo pedido de documento não reconhecido: %s", argumentos.get("documento"))
            return "Documento não reconhecido. Use os ids do catálogo."
        if not item.resumo:
            log.info("[%s] ainda não tem resumo", item.id)
            return (f"[{item.id}] ainda não tem resumo (rode python -m sensorchat descrever). "
                    "Use buscar_na_base.")
        return f"RESUMO DE [{item.id}] {item.arquivo}:\n\n{item.resumo}"

    def _busca_automatica(self, pergunta, cotas):
        try:
            return self._busca.buscar_por_cotas(pergunta, cotas, self._trechos)
        except NenhumaBaseDisponivel:
            return []
