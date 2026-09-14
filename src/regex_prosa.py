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

# A peça também invoca o precedente ou a norma sem nomear nem número nem
# tribunal: "a jurisprudência pacífica desta Corte", "o verbete sumular
# aplicável à espécie", "a lei que disciplina a prescrição no caso". A
# referência é real e resolve para nada, o que a torna `incompleta`.
#
# A fórmula tem três peças que variam de forma independente: o que se
# invoca, o adjetivo que o qualifica e o complemento que o situa, seja o
# órgão que o firmou, seja o alcance da matéria. O padrão descreve as
# peças, e não as combinações observadas, para que uma redação ainda não
# vista continue reconhecível.
_NUCLEO_VAGO = (
    r"(?:jurisprud[êe]nc?[eil]?[ia]a?|orienta[çc][ãa]o|entendi\w{0,2}ento"
    r"|precedentes?|ac[óo]rd[ãa]os?|verbete\s+sumular|enunciado(?:\s+sumular)?"
    r"|s[úu]mula|tese|dispositivos?|preceito|lei|leis|normas?|regra)"
)
_ADJETIVO_VAGO = (
    r"(?:reiterad|iterativ|not[óo]ri|pac[íi]fic|consolidad|sumulad|dominante"
    r"|vinculante|recente|firmad|assentad|uniforme|remans|jurisprudencial"
    r"|legal|legais|constitucional)[oa]?s?"
)
# O órgão que firmou o entendimento, nomeado sem identificar julgado algum.
_ORGAO_VAGO = (
    r"(?:desta\s+Corte|desta\s+Casa|pel[ao]\s+Corte|d[ao]\s+Corte(?:\s+Superior)?"
    r"|d[ao]\s+Tribunal(?:\s+Superior)?|dos\s+tribunais\s+superiores"
    r"|d[ao]s?\s+inst[âa]ncias?\s+superior(?:es)?"
    r"|d[ao]\s+(?:Primeira|Segunda|Terceira|Quarta|Quinta|Sexta)\s+Turma"
    r"|d[ao]\s+[ÓO]rg[ãa]o\s+Especial|d[ao]\s+Tribunal\s+Pleno)"
)
# O alcance da referência, no lugar do órgão ou depois dele.
_ESCOPO_VAGO = (
    r"(?:sobre\s+a\s+mat[ée]ria|aplic[áa]vel\s+[àa]\s+esp[ée]cie|pertinente"
    r"|invocad[oa]\s+na\s+origem|de\s+reg[êe]ncia(?:\s+da\s+mat[ée]ria)?"
    r"|aplic[áa]vel|que\s+(?:disciplina|rege)\s+[^,.]{3,40}"
    r"|em\s+sede\s+de\s+recurso\s+repetitivo|em\s+repercuss[ãa]o\s+geral"
    r"|em\s+situa[çc][õo]es\s+an[áa]logas)"
)
_COMPLEMENTO_VAGO = rf"(?:{_ORGAO_VAGO}|{_ESCOPO_VAGO})"

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
    # "a jurisprudência pacífica desta Corte". A ressalva ao fim separa a
    # invocação de um precedente da afirmação de que a jurisprudência está
    # assentada, que é argumentação: "a orientação dos tribunais superiores
    # é firme no ponto".
    rf"\b(?:{_ADJETIVO_VAGO}\s+)?{_NUCLEO_VAGO}(?:\s+{_ADJETIVO_VAGO})?"
    rf"(?:\s+{_COMPLEMENTO_VAGO})(?:\s+{_COMPLEMENTO_VAGO})?(?!\s+[ée]\s+firme)",
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
