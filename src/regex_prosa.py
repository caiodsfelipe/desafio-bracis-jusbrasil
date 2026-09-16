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
# A espécie do recurso substitui o tribunal como elemento que situa o
# julgado: "Rcl de 2021, Rel. Min. Rosa Weber" identifica um acórdão sem
# nomear a corte. A lista é de siglas correntes no processo brasileiro, e
# não das que aparecem nestes documentos.
_ESPECIE_DE_RECURSO = (
    r"(?:Reclama[çc][ãa]o|Rcl|APL|Apela[çc][ãa]o|AgRg|AgInt|AgR|EDcl|ED"
    r"|RHC|RMS|ROMS|HC|MS|RE|REsp|AREsp|ARE|RR|AIRR|ARR|RSE|RO|ROC"
    r"|ADI|ADC|ADPF|ADO|CC|Pet|AC|AI|SL|SS|QO|EREsp|EDiv"
    r"|Agravo(?:\s+\w+){0,4}|Recurso(?:\s+\w+){0,4}"
    r"|Habeas\s+Corpus|Mandado\s+de\s+Seguran[çc]a"
    r"|A[çc][ãa]o\s+(?:Direta|Declarat[óo]ria|Rescis[óo]ria)(?:\s+\w+){0,3}"
    r"|Conflito\s+de\s+Compet[êe]ncia|Peti[çc][ãa]o|Suspens[ãa]o(?:\s+\w+){0,4})"
)

_TRIBUNAL = (
    r"(?:STF|STJ|TST|TSE|STM|TRF\s?\d?|TJ[A-Z]{2}|TRT\s?\d{0,2}|TRE[-\s]?[A-Z]{2}"
    r"|Supremo Tribunal Federal|Superior Tribunal de Justi[çc]a"
    r"|Tribunal Superior do Trabalho|Tribunal Superior Eleitoral"
    r"|Superior Tribunal Militar"
    # os regionais nomeiam a região por extenso: "TRT da 2ª Região"
    r"|Tribunal Regional (?:Federal|do Trabalho|Eleitoral)"
    r"(?:\s+d[ae]\s+\d{1,2}[ªa]?\s+Regi[ãa]o)?"
    r"|TR[FTE]\s+d[ae]\s+\d{1,2}[ªa]?\s+Regi[ãa]o"
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
# meio: "José Roberto Freire Pimenta", "ARTUR VIDIGAL DE OLIVEIRA". O ponto
# só continua o nome quando encerra uma abreviatura ("Min.", "Rel."), e não
# quando encerra a frase, para que o span pare no último elemento do nome.
_PALAVRA_DE_NOME = (
    r"[A-ZÀ-Ý][\wÀ-ÿ]{0,2}\.(?=\s*[A-ZÀ-Ý])|[A-ZÀ-Ý][\wÀ-ÿ]*"
)
_NOME = rf"(?:{_PALAVRA_DE_NOME})(?:\s+(?:d[aeo]s?|e|{_PALAVRA_DE_NOME})){{0,5}}"

# A digitalização confunde "e" com "c", e "de" chega como "dc".
_DE = r"d[ceo]"
_ANO = r"(?:19|20)\d{2}"
_LIGACAO = r"(?:d[oaes]|pel[oa])s?"

# Quem conduziu o julgamento, nomeado por relatoria, por lavra, por
# relato ou pela abreviatura que antecede o nome.
_RELATOR = (
    rf"(?:(?:pela|sob|d[ao]|{_DE})\s+(?:relatoria|lavra)\s+(?:{_DE}|d[ao])?\s*"
    rf"(?:Min(?:istr[oa])?\.?|Des(?:embargador[a]?)?\.?)?\s*{_NOME}"
    rf"|relatad[oa]\s+pel[oa]\s+(?:Min(?:istr[oa])?\.?|Des(?:embargador[a]?)?\.?)?\s*{_NOME}"
    rf"|Rel(?:at[oa]r[a]?)?\.?\s*(?:Min(?:istr[oa])?\.?|Des(?:embargador[a]?)?\.?)?\s*{_NOME})"
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

# A citação identifica o julgado por três elementos, e o órgão sozinho não
# basta: "reiterados precedentes do Superior Tribunal de Justiça" aponta um
# conjunto difuso, não um acórdão, e não é citação. O ano ou o relator é o
# que estreita a referência a um julgado determinado.
_DATA_OU_RELATOR = rf"(?:{_DATA}(?:[\s,]*{_RELATOR})?|[\s,]*{_RELATOR})"

_PADROES = (
    # "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli",
    # "entendimento firmado pelo STJ em 2021"
    rf"\b{_QUALIFICADOR}{_TERMO_JURISPRUDENCIAL}\s+{_PARTICIPIO_DE_LIGACAO}"
    rf"{_LIGACAO}\s+{_ORGAO_JULGADOR}(?![\wÀ-ÿ]){_DATA_OU_RELATOR}",
    # "Reclamação do STF, de 2025, Rel. Min. CRISTIANO ZANIN"
    rf"\b{_ESPECIE_DE_RECURSO}\s+d[oa]\s+{_ORGAO_JULGADOR}{_DATA}[\s,]*{_RELATOR}",
    # "Rcl de 2021, Rel. Min. Rosa Weber"
    rf"\b{_ESPECIE_DE_RECURSO}\s+(?:em|{_DE})\s*{_ANO}[\s,]*{_RELATOR}",
)

_COMPILADOS = tuple(re.compile(p) for p in _PADROES)


# Um julgado referido em prosa nomeia o tribunal que o proferiu ou o
# relator que o conduziu. O substantivo sozinho não basta: "o acórdão
# recorrido" e "a jurisprudência pacífica desta Corte" apontam a decisão
# em julgamento ou um entendimento difuso, não um precedente identificável,
# e nenhum dos dois é citação.
def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Spans (inicio, fim, trecho) das citações sem identificador."""
    candidatos = []
    for padrao in _COMPILADOS:
        for m in padrao.finditer(texto):
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
