"""
Extração das citações que descrevem o julgado sem dar seu número.

São referências como "julgado do STF proferido em 2024 pela relatoria de
Dias Toffoli": identificam o precedente pelo órgão julgador, pelo ano e
pelo relator. Nenhuma resolve para um registro do acervo, porque esses três
elementos descrevem muitos acórdãos ao mesmo tempo, e a citação é sempre
`incompleta`.

A citação é montada a partir de três peças que variam de forma
independente: como a peça se refere ao julgado, qual o órgão julgador, e
quais complementos acompanham. O padrão descreve as peças, não as
combinações, de modo que uma forma ainda não vista continue reconhecível.
"""
import re

# Como a peça se refere ao julgado, sem nomear a espécie de recurso.
_TERMO_JURISPRUDENCIAL = (
    r"(?:julgad[oa]s?|precedentes?|ac[óo]rd[ãa]os?|decis(?:[ãa]o|[õo]es)"
    r"|arestos?|entendimentos?|jurisprud[êe]ncia"
    r"|orienta[çc][ãa]o\s+jurisprudencial)"
)

# A espécie do recurso, quando é ela que abre a citação.
_ESPECIE_DE_RECURSO = (
    r"(?:Reclama[çc][ãa]o|Rcl|APL|Apela[çc][ãa]o|AgRg|AgInt|EDcl|RHC|RMS"
    r"|Agravo(?:\s+\w+){0,4}|Recurso(?:\s+\w+){0,4}"
    r"|Habeas\s+Corpus|Mandado\s+de\s+Seguran[çc]a)"
)

_TRIBUNAL = (
    r"(?:STF|STJ|TST|TSE|STM|TRF\s?\d?|TJ[A-Z]{2}|TRT\s?\d{0,2}|TRE[-\s]?[A-Z]{2}"
    r"|Supremo Tribunal Federal|Superior Tribunal de Justi[çc]a"
    r"|Tribunal Superior do Trabalho|Tribunal Superior Eleitoral"
    r"|Superior Tribunal Militar"
    r"|Tribunal de Justi[çc]a(?:\s+d[eo]\s+[A-ZÀ-Ý][\wÀ-ÿ]*){0,3})"
)

# O órgão fracionário antecede o tribunal: "da Segunda Turma do STF", "da
# Corte Especial do STJ".
_ORGAO_FRACIONARIO = (
    r"(?:(?:(?:Primeira|Segunda|Terceira|Quarta|Quinta|Sexta|S[ée]tima|Oitava|\d[ªa])"
    r"\s+(?:Turma|Se[çc][ãa]o|C[âa]mara)|Corte Especial|Tribunal Pleno|[ÓO]rg[ãa]o Especial)"
    r"\s+d[oa]\s+)?"
)
_ORGAO_JULGADOR = rf"{_ORGAO_FRACIONARIO}{_TRIBUNAL}"

# O nome do relator vem em maiúsculas ou capitalizado, com preposições no
# meio: "José Roberto Freire Pimenta", "ARTUR VIDIGAL DE OLIVEIRA".
_NOME = r"[A-ZÀ-Ý][\wÀ-ÿ.]*(?:\s+(?:d[aeo]s?|e|[A-ZÀ-Ý][\wÀ-ÿ.]*)){0,5}"

# A digitalização confunde "e" com "c", e "de" chega como "dc".
_DE = r"d[ceo]"
_ANO = r"(?:19|20)\d{2}"
_LIGACAO = r"(?:d[oaes]|pel[oa])s?"

_RELATOR = (
    rf"(?:(?:pela|sob|d[ao]|{_DE})\s+relatoria\s+(?:{_DE}|d[ao])?\s*{_NOME}"
    rf"|Rel(?:at[oa]r[a]?)?\.?\s*(?:Min(?:istr[oa])?\.?)?\s*{_NOME})"
)

# Entre o órgão e o ano cabe um particípio ("proferido", "julgado"), que a
# digitalização corrompe; por isso entra como palavra qualquer.
_DATA = rf"(?:[\s,]*(?:\w+\s+)?(?:em|{_DE})\s*{_ANO})"

# O adjetivo que qualifica o julgado faz parte da citação, como em
# "reiterados precedentes". Entre o termo e o órgão cabe ainda o particípio
# que os liga ("firmado", "consolidada").
_QUALIFICADOR = (
    r"(?:(?:reiterad|iterativ|not[óo]ri|pac[íi]fic|remans)[oa]s?\s+)?"
)
# O particípio que liga o termo ao órgão, quando existe: "entendimento
# firmado pelo STJ", "jurisprudência consolidada do TST". A palavra de
# ligação que vem em seguida não serve como particípio.
_PARTICIPIO_DE_LIGACAO = rf"(?:(?!{_LIGACAO}\s)[a-zà-ÿ]{{3,}}[oa]s?\s+)?"

_PADROES = (
    # "reiterados precedentes do Superior Tribunal de Justiça",
    # "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli",
    # "entendimento firmado pelo STJ em 2021"
    rf"\b{_QUALIFICADOR}{_TERMO_JURISPRUDENCIAL}\s+{_PARTICIPIO_DE_LIGACAO}"
    rf"{_LIGACAO}\s+{_ORGAO_JULGADOR}(?![\wÀ-ÿ])"
    rf"{_DATA}?(?:[\s,]*{_RELATOR})?",
    # "Reclamação do STF, de 2025, Rel. Min. CRISTIANO ZANIN"
    rf"\b{_ESPECIE_DE_RECURSO}\s+d[oa]\s+{_ORGAO_JULGADOR}{_DATA}[\s,]*{_RELATOR}",
    # "Rcl de 2021, Rel. Min. Rosa Weber"
    rf"\b{_ESPECIE_DE_RECURSO}\s+(?:em|{_DE})\s*{_ANO}[\s,]*{_RELATOR}",
    # "artigo correspondente do Código de Processo Civil"
    r"\bartigos?\s+correspondentes?\s+d[oa]\s+"
    r"[A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+(?:d[aeo]s?|[A-ZÀ-Ý][\wÀ-ÿ]*)){0,5}",
)

_COMPILADOS = tuple(re.compile(p) for p in _PADROES)


# Um julgado referido em prosa nomeia o tribunal que o proferiu ou o
# relator que o conduziu. O substantivo sozinho não basta: "o acórdão
# recorrido" e "a jurisprudência pacífica desta Corte" apontam a decisão
# em julgamento ou um entendimento difuso, não um precedente identificável,
# e nenhum dos dois é citação.
# A citação a norma sem número nomeia o diploma no lugar do tribunal.
_DIPLOMA_CITADO = (
    r"C[óo]digo\b|Constitui[çc][ãa]o|Consolida[çc][ãa]o\s+das\s+Leis"
    r"|Lei\s+(?:Complementar|n)|CPC|CPP|CLT|CDC|CPM|CF/"
)
_MARCA_DE_CITACAO = re.compile(
    rf"{_TRIBUNAL}|Rel(?:at[oa]r[a]?)?\.|Min(?:istr[oa])?\.|relatoria|{_DIPLOMA_CITADO}"
)


def tem_marca_de_julgado(trecho: str) -> bool:
    """O trecho nomeia quem julgou ou qual norma se invoca.

    Serve para corroborar um trecho que só o modelo apontou: os padrões
    descrevem as formas conhecidas de citação, e o que escapa a todas elas
    precisa ao menos nomear um tribunal, um relator ou um diploma.
    """
    return bool(_MARCA_DE_CITACAO.search(trecho))


def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Spans (inicio, fim, trecho) das citações sem identificador."""
    candidatos = []
    for padrao in _COMPILADOS:
        for m in padrao.finditer(texto):
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
