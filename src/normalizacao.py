# -*- coding: utf-8 -*-
"""
Normalização do identificador numérico de uma citação.

Opera apenas dentro do span já delimitado como citação, nunca sobre o
documento inteiro: a tradução de letras em dígitos só faz sentido onde já
se sabe haver um número.

Os documentos trazem identificadores com ruído de digitalização — letras
no lugar de dígitos, espaço no meio do número, pontuação parcial ou
ausente. A saída é a forma que o acervo usa, que é como o índice FTS5
consegue casá-la.
"""
import re

MAPA_OCR = {
    "O": "0", "o": "0",
    "l": "1", "I": "1",
    "S": "5", "s": "5",
    "G": "6",
    "g": "9",
}

_CHARS_NUMERICOS = "0-9OolIGgSs"

# Um bloco numérico admite ponto, traço e espaço entre dois caracteres,
# nunca nas bordas: o espaço aparece como separador de milhar ruidoso
# ("1 307 026"), e sem aceitá-lo o número se fragmentaria em pedaços curtos
# demais para identificar coisa alguma. O hífen cercado de espaços é
# exceção — separa a UF do número ("21737l8 - SP") e não faz parte dele.
_UNIDADE_NUMERICA = rf"[{_CHARS_NUMERICOS}]"
_COLA = rf"(?:{_UNIDADE_NUMERICA}|\.|-(?!\s)(?<!\s-)| )"
_BLOCO_CANDIDATO = re.compile(
    rf"{_UNIDADE_NUMERICA}(?:{_COLA}*{_UNIDADE_NUMERICA})?"
)


def _eh_letra_isolada(bloco: str, i: int) -> bool:
    """A letra na posição i não encosta em nenhum dígito, logo não é um
    dígito grafado incorretamente."""
    if bloco[i] not in MAPA_OCR:
        return False
    anterior = bloco[i - 1] if i > 0 else ""
    seguinte = bloco[i + 1] if i + 1 < len(bloco) else ""
    return not (anterior.isdigit() or seguinte.isdigit())


def _aparar_letras_isoladas(bloco: str) -> str:
    """Remove das bordas do bloco as letras que não pertencem ao número,
    como a última letra de uma abreviação vizinha."""
    inicio, fim = 0, len(bloco)
    while inicio < fim and _eh_letra_isolada(bloco, inicio):
        inicio += 1
    while fim > inicio and _eh_letra_isolada(bloco, fim - 1):
        fim -= 1
    return bloco[inicio:fim]


def _traduzir_letras(bloco: str) -> str:
    """Converte em dígito cada letra encostada num dígito verdadeiro,
    preservando as demais."""
    resultado = []
    for i, ch in enumerate(bloco):
        if ch in MAPA_OCR and not _eh_letra_isolada(bloco, i):
            resultado.append(MAPA_OCR[ch])
        else:
            resultado.append(ch)
    return "".join(resultado)


def _reagrupar(digitos: str) -> str:
    """Insere o separador de milhar: '2173718' vira '2.173.718'."""
    partes = []
    while digitos:
        partes.append(digitos[-3:])
        digitos = digitos[:-3]
    return ".".join(reversed(partes))


_DIGITOS_CNJ = 20


def _formatar_cnj(digitos: str) -> str:
    """Aplica a máscara do número único do CNJ, cuja estrutura é fixa:
    sequencial, dígito verificador, ano, segmento, tribunal e origem.
    '06003164920206160182' vira '0600316-49.2020.6.16.0182'."""
    return (
        f"{digitos[:7]}-{digitos[7:9]}.{digitos[9:13]}"
        f".{digitos[13]}.{digitos[14:16]}.{digitos[16:20]}"
    )


def _normalizar_bloco(bloco: str) -> str:
    bloco = _aparar_letras_isoladas(bloco)
    traduzido = _traduzir_letras(bloco)
    so_digitos = re.sub(r"\D", "", traduzido)

    if len(so_digitos) == _DIGITOS_CNJ:
        return _formatar_cnj(so_digitos)
    if any(c in ".-" for c in bloco):
        # a pontuação original já estrutura o número; o espaço é ruído
        return traduzido.replace(" ", "").replace("\xa0", "")
    return _reagrupar(so_digitos)


# Ano precedido de preposição é a data do julgamento, não um identificador.
_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+((?:19|20)\d{2})\b", re.IGNORECASE)


def normalizar_identificadores(span: str) -> list[str]:
    """Identificadores normalizados presentes no span, um por bloco
    numérico. Lista vazia quando a citação não traz identificador — o
    julgado referido apenas por tribunal, ano e relator."""
    anos_de_julgado = set(_PREPOSICAO_ANO.findall(span))
    identificadores = []
    for bloco in _BLOCO_CANDIDATO.findall(span):
        if not any(c.isdigit() for c in bloco):
            continue
        normalizado = _normalizar_bloco(bloco)
        if normalizado.replace(".", "") in anos_de_julgado:
            continue
        identificadores.append(normalizado)
    return identificadores
