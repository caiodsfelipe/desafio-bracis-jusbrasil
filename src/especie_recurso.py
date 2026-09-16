"""
Família do recurso a que um processo pertence.

Um mesmo número percorre várias espécies ao longo da tramitação: o recurso
de revista, o agravo de instrumento que o precede e o agravo interno que o
segue compartilham o número e formam uma família. Espécies de famílias
diferentes com o mesmo número são processos sem relação entre si, e é essa
distinção que separa uma citação legítima de uma inventada quando o número
existe no acervo mas pertence a outro tipo de feito.

A sigla é lida tanto da citação quanto do texto ao redor da ocorrência no
acervo, e as duas precisam concordar.
"""
import re

_FAMILIA_POR_SIGLA = {
    "AGARR": "revista",
    "AIRR": "revista",
    "ARR": "revista",
    "RR": "revista",
    "ARESP": "especial",
    "AGINT": "especial",
    "EDCL": "especial",
    "RESPE": "eleitoral",
    "RESP": "especial",
    "RCL": "reclamacao",
    "RMS": "mandado",
    "MS": "mandado",
    "RHC": "habeas",
    "HC": "habeas",
    "RE": "extraordinario",
    "APL": "apelacao",
    "RSE": "sentido_estrito",
}

# O nome por extenso decide antes da sigla: um acórdão que se anuncia como
# "MANDADO DE SEGURANÇA" traz a sigla MS adiante, e ler o nome evita
# depender de onde a sigla aparece.
_FAMILIA_POR_EXTENSO = {
    "RECLAMA": "reclamacao",
    "MANDADO DE SEGURAN": "mandado",
    "HABEAS CORPUS": "habeas",
    "RECURSO DE REVISTA": "revista",
    "AGRAVO DE INSTRUMENTO": "revista",
    "RECURSO ESPECIAL": "especial",
    "RECURSO EXTRAORDIN": "extraordinario",
    "APELA": "apelacao",
    "SENTIDO ESTRITO": "sentido_estrito",
}

_SIGLAS_POR_TAMANHO = sorted(_FAMILIA_POR_SIGLA, key=len, reverse=True)

# Quanto do texto ao redor da ocorrência nomeia a espécie: a designação vem
# imediatamente antes do número.
_CONTEXTO_ANTES = 80
_CONTEXTO_DEPOIS = 10


def familia(texto: str) -> str | None:
    """Família do recurso nomeado no texto, ou None quando nenhuma aparece."""
    maiusculo = texto.upper()
    for nome, familia_do_nome in _FAMILIA_POR_EXTENSO.items():
        if nome in maiusculo:
            return familia_do_nome
    for sigla in _SIGLAS_POR_TAMANHO:
        if re.search(rf"(?:\b|-){sigla}(?:\b|-)", maiusculo):
            return _FAMILIA_POR_SIGLA[sigla]
    return None


def familia_da_ocorrencia(texto: str, inicio: int) -> str | None:
    """Família nomeada ao redor da ocorrência do número no acervo."""
    janela = texto[max(0, inicio - _CONTEXTO_ANTES) : inicio + _CONTEXTO_DEPOIS]
    return familia(" ".join(janela.split()))


# A fórmula de autuação abre o acórdão e apresenta os autos que ele julga:
# "Vistos, relatados e discutidos estes autos de Recurso de Revista nº X".
# Onde ela antecede o número, o acórdão é o processo; onde falta, o número
# está sendo transcrito de outro feito.
_FORMULA_DE_AUTUACAO = re.compile(
    r"Vistos,?\s+relatados|estes\s+autos\s+de|autos\s+em\s+que", re.IGNORECASE
)


def autua_o_processo(texto: str, inicio: int) -> bool:
    """O número é apresentado como os autos que o acórdão julga."""
    antes = texto[max(0, inicio - _CONTEXTO_ANTES) : inicio]
    return bool(_FORMULA_DE_AUTUACAO.search(" ".join(antes.split())))
