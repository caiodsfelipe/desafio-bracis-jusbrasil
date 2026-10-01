"""
Normalização do identificador numérico de uma citação.

Opera apenas dentro do span já delimitado como citação, nunca sobre o
documento inteiro: a tradução de letras em dígitos só faz sentido onde já
se sabe haver um número.

Os documentos trazem identificadores com ruído de digitalização: letras
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

# Um bloco numérico admite ponto, traço e espaço em branco entre dois
# caracteres, nunca nas bordas: a digitalização quebra o número em qualquer
# ponto, e o que separa dois pedaços pode ser um espaço ("1 307 026"), uma
# quebra de linha ("...5.24.\n0091") ou uma sequência de pontuação
# ("33.-\n474"). Sem aceitá-los o número se fragmentaria em pedaços curtos
# demais para identificar coisa alguma, e pedaços curtos casam com
# documentos que não têm relação com a citação.
_UNIDADE_NUMERICA = rf"[{_CHARS_NUMERICOS}]"
_SEPARADOR_INTERNO = r"[.\-]|[ \n\r\t\xa0]"
_COLA = rf"(?:{_UNIDADE_NUMERICA}|{_SEPARADOR_INTERNO})"
_BLOCO_CANDIDATO = re.compile(
    rf"{_UNIDADE_NUMERICA}(?:{_COLA}*{_UNIDADE_NUMERICA})?"
)

# Pontuação e espaço que sobram nas bordas depois de descartada uma letra
# vizinha: em "21737l8 - SP" a sigla da UF sai como letra isolada e deixa
# atrás de si o hífen que a separava do número.
_BORDAS_DESCARTAVEIS = ".- \n\r\t\xa0"


# Entre a letra e o dígito que a acompanha pode haver o separador de
# milhar: em "l.234.567" o "l" é o algarismo inicial do número. Só o ponto
# separa milhares; o hífen e o espaço separam o número da sigla da UF, e
# atravessá-los faria do "S" de "SP" um algarismo.
_SEPARADOR_DE_MILHAR = "."


def _vizinho_numerico(bloco: str, i: int, passo: int) -> bool:
    """Há um dígito adiante na direção dada, alcançável atravessando
    apenas o separador de milhar."""
    j = i + passo
    while 0 <= j < len(bloco):
        if bloco[j].isdigit():
            return True
        if bloco[j] != _SEPARADOR_DE_MILHAR:
            return False
        j += passo
    return False


def _eh_letra_isolada(bloco: str, i: int) -> bool:
    """A letra na posição i não acompanha nenhum dígito, logo não é um
    dígito grafado incorretamente."""
    if bloco[i] not in MAPA_OCR:
        return False
    return not (
        _vizinho_numerico(bloco, i, -1) or _vizinho_numerico(bloco, i, 1)
    )


def _aparar_letras_isoladas(bloco: str) -> str:
    """Remove das bordas do bloco as letras que não pertencem ao número,
    como a última letra de uma abreviação vizinha."""
    inicio, fim = 0, len(bloco)
    while inicio < fim and _eh_letra_isolada(bloco, inicio):
        inicio += 1
    while fim > inicio and _eh_letra_isolada(bloco, fim - 1):
        fim -= 1
    return bloco[inicio:fim].strip(_BORDAS_DESCARTAVEIS)


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
        # a pontuação original já estrutura o número; o espaço em branco
        # que a digitalização deixou entre os pedaços é ruído
        return re.sub(r"[ \n\r\t\xa0]", "", traduzido)
    return _reagrupar(so_digitos)


# Ano precedido de preposição é a data do julgamento, não um identificador.
_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+((?:19|20)\d{2})\b", re.IGNORECASE)

# O dígito colado à sigla do tribunal identifica a região, não o processo:
# em "TRF1" e "TRT 15" o número faz parte do nome do órgão, e sozinho casa
# com metade do acervo.
_DIGITO_DE_ORGAO = re.compile(
    r"\b(?:TRF|TRT|TRE|CJF|JEF)\s*-?\s*(\d{1,2})\b", re.IGNORECASE
)

# Um identificador de processo tem mais de um algarismo; um só é resto de
# sigla, de inciso ou de numeração de item.
_MINIMO_DE_ALGARISMOS = 2

# O ano do julgamento acompanha o número do processo em boa parte das
# citações ("Petição 45.556/2023", "REsp 1.234.567/SP, julgado em
# 12/03/2024"), e a preposição nem sempre o antecede, de modo que
# _PREPOSICAO_ANO não o alcança. Sozinho ele não identifica processo algum,
# mas o FTS5 ignora o separador de milhar e busca "2.023" como o par de
# tokens "2 023", que casa com o sequencial de um acórdão sem relação com a
# citação. Como são poucos os registros assim atingidos, o número escapa do
# filtro de ambiguidade, e um processo que o acervo não contém seria dado por
# `real` com o link errado, que é o erro que a métrica mais pune.
#
# O ano só é descartado quando acompanha outro identificador. A citação que
# traz apenas um número com forma de ano continua resolvendo por ele, já
# que nesse caso não há o que contaminar.
_ANO_ISOLADO = re.compile(r"^(?:19|20)\d{2}$")


def _identifica_processo(algarismos: str, total_de_blocos: int) -> bool:
    """O bloco identifica o processo, e não a data do julgamento."""
    if len(algarismos) < _MINIMO_DE_ALGARISMOS:
        return False
    return not (total_de_blocos > 1 and _ANO_ISOLADO.match(algarismos))


def normalizar_identificadores(span: str) -> list[str]:
    """Identificadores normalizados presentes no span, um por bloco
    numérico. Lista vazia quando a citação não traz identificador, caso do
    julgado referido apenas por tribunal, ano e relator."""
    descartados = set(_PREPOSICAO_ANO.findall(span))
    descartados.update(_DIGITO_DE_ORGAO.findall(span))
    normalizados = []
    for bloco in _BLOCO_CANDIDATO.findall(span):
        if not any(c.isdigit() for c in bloco):
            continue
        normalizado = _normalizar_bloco(bloco)
        algarismos = re.sub(r"\D", "", normalizado)
        if algarismos in descartados:
            continue
        normalizados.append((normalizado, algarismos))
    return [
        normalizado
        for normalizado, algarismos in normalizados
        if _identifica_processo(algarismos, len(normalizados))
    ]
