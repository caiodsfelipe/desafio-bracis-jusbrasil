"""
Extração de citações com identificador por padrões estruturais.

Cobre as citações que trazem número de processo, de súmula, de tema ou de
artigo de lei. As que descrevem o julgado sem dar seu número ficam em
regex_prosa.py, e o extrator via LLM (prompt_extracao.py) recolhe as formas
que nenhum padrão previu; as três fontes percorrem o mesmo texto e seus
resultados são mesclados em extracao.py.
"""
import re

# O nome do recurso encadeia palavras em maiúscula ligadas por preposições
# e pela conjunção, como em "Suspensão de Liminar e de Sentença".
_CONECTORES = r"(?:em|no|na|nos|nas|de|da|do|das|dos|e)"
# O "N" de "Nº" pertence ao conector do número, não ao nome do recurso.
_TOKEN_MAIUSCULO = r"(?!N[º°](?!\w))[A-ZÀ-Ý][A-Za-zÀ-ÿ.\-]*"
_CONECTOR_NUMERO = r"(?:[nN][º°o.]\s*)?"

# A digitalização troca dígitos por letras parecidas ("6G.838" por "68.838",
# "170076O" por "1700760"). Elas contam como parte do número quando há um
# dígito verdadeiro ao alcance; fora disso são texto, e incluí-las engoliria
# a sigla da UF que vem depois do número.
_LETRAS_OCR = "OolIGgSs"
_UNIDADE = rf"(?:\d|[{_LETRAS_OCR}](?=[\d.\-]*\d))"
_CORPO_IDENTIFICADOR = rf"(?:{_UNIDADE}|[.\-/:°ºnN() \n\xa0])*"
# O número termina em dígito, ou na letra que substitui o último dígito,
# nunca numa letra que inicia a palavra seguinte.
_FIM_IDENTIFICADOR = rf"(?:\d|(?<=\d)[{_LETRAS_OCR}](?![A-Za-zÀ-ÿ]))"
# O número tem ao menos dois algarismos: um dígito solto é parte do texto,
# não identificador de processo.
_IDENTIFICADOR = rf"\d{_CORPO_IDENTIFICADOR}{_FIM_IDENTIFICADOR}"
_SUFIXO_UF = r"(?:\s*[-/–(]\s*[A-Z]{2}\)?)?"

_PADRAO_CITACAO = re.compile(
    rf"{_TOKEN_MAIUSCULO}(?:\s+(?:{_TOKEN_MAIUSCULO}|{_CONECTORES})){{0,12}}"
    rf"\s*{_CONECTOR_NUMERO}{_IDENTIFICADOR}{_SUFIXO_UF}"
)

# O "S" inicial e o acento sofrem a mesma troca de digitalização que os
# números, e a palavra aparece abreviada ("Súm. 166 do TSE").
_PADRAO_SUMULA = re.compile(
    r"[S5][uúUÚ]m(?:ula)?\.?(?:\s+Vinculante)?\s+\d+(?:\s+d[oa]\s+[A-ZÀ-Ý]+)?",
    re.IGNORECASE,
)

# Tema de repercussão geral e tema de recursos repetitivos identificam o
# precedente pelo número do tema, não pelo número do processo.
_PADRAO_TEMA = re.compile(
    r"\bTem[aãáà]\s+\d[\d.]*"
    r"(?:\s+d[oa]s?\s+(?:repercuss[ãa]o\s+geral|recursos?\s+repetitivos?))?",
    re.IGNORECASE,
)

# Dispositivo de lei: "art. 373, I, do CPC", "artigo 7º, XXIX, da
# Constituição Federal", "art. 1º, I, 'g', da Lei Complementar nº 64/1990".
# O diploma faz parte da identidade da citação, já que o mesmo número de
# artigo existe em códigos diferentes, por isso o padrão vai até ele.
_INCISOS = r"(?:\s*,\s*(?:[IVXLC]+|[a-z]|§\s*\d+[º°]?(?:-[A-Z])?|'[a-z]'|\"[a-z]\"))*"
# O nome do diploma começa em maiúscula ou é uma sigla, e admite
# conectores em minúscula e quebra de linha adiante.
_PALAVRA_DIPLOMA = r"(?:[A-ZÀ-Ý][a-zà-ÿ]+|d[aeo]s?|e)"
_DIPLOMA = (
    r"(?:[A-ZÀ-Ý]{2,}"                                   # sigla: CPC, CLT, CDC
    rf"|[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+{_PALAVRA_DIPLOMA}){{0,5}}"  # ou nome por extenso
    r"(?:\s*n[º°.]?\s*[\d./-]+)?)"                       # e eventual "nº 9.504/1997"
)
# A distinção de caixa delimita o nome do diploma, separando-o do texto
# que vem depois; por isso o padrão é sensível a maiúsculas.
_PADRAO_ARTIGO = re.compile(
    rf"\b[Aa]rt(?:igo)?\.?\s*\d{{1,3}}(?:\.\d{{3}})*[º°]?{_INCISOS}"
    rf"\s*,?\s*d[aeo]s?\s+{_DIPLOMA}"
)

# Um ano precedido de preposição encerra uma citação em prosa, não um
# identificador de processo.
_PADRAO_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+\d{4}$", re.IGNORECASE)


def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Spans (inicio, fim, trecho) das citações com identificador. A
    decomposição do número fica para normalizacao.py."""
    candidatos = []
    for padrao in (_PADRAO_CITACAO, _PADRAO_SUMULA, _PADRAO_ARTIGO, _PADRAO_TEMA):
        for m in padrao.finditer(texto):
            if _PADRAO_PREPOSICAO_ANO.search(m.group()):
                continue
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
