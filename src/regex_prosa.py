# -*- coding: utf-8 -*-
"""
Extração das citações que descrevem o julgado sem dar seu número.

São referências como "julgado do STF proferido em 2024 pela relatoria de
Dias Toffoli": identificam o precedente por tribunal, ano e relator, e
nenhuma delas resolve para um registro do acervo — a busca por esses três
elementos devolve muitos acórdãos, e a citação é sempre `incompleta`.

A forma é fixa o bastante para ser descrita por padrão. O que varia é o
substantivo que abre a citação, a presença do ano e do relator, e o ruído
de digitalização; o tribunal e a estrutura da frase permanecem.
"""
import re

_TRIBUNAL = (
    r"(?:STF|STJ|TST|TSE|STM|TRF\d?|TJ[A-Z]{2}"
    r"|Supremo Tribunal Federal|Superior Tribunal de Justi[çc]a"
    r"|Tribunal Superior do Trabalho|Tribunal Superior Eleitoral"
    r"|Superior Tribunal Militar)"
)

# O nome do relator vem em maiúsculas ou capitalizado, com preposições no
# meio ("José Roberto Freire Pimenta", "ARTUR VIDIGAL DE OLIVEIRA").
_NOME = r"[A-ZÀ-Ý][\wÀ-ÿ.]*(?:\s+(?:d[aeo]s?|e|[A-ZÀ-Ý][\wÀ-ÿ.]*)){0,5}"

# A digitalização confunde "e" com "c": "de" aparece como "dc".
_DE = r"d[ceo]"
_ANO = r"(?:19|20)\d{2}"

_RELATOR = (
    rf"(?:(?:pela|sob|d[ao]|{_DE})\s+relatoria\s+(?:{_DE}|d[ao])?\s*{_NOME}"
    rf"|Rel\.?\s*Min\.?\s*{_NOME})"
)

# Como a peça se refere ao julgado: pelo substantivo genérico, ou pelo nome
# da espécie de recurso.
_GENERICO = r"(?:julgados?|precedentes?|ac[óo]rd[ãa]os?|decis[ãõ]e?s?)"
_RECURSO = (
    r"(?:Reclama[çc][ãa]o|Rcl|APL|Apela[çc][ãa]o|Agravo(?:\s+\w+){0,4}"
    r"|Recurso(?:\s+\w+){0,4}|Habeas\s+Corpus|Mandado\s+de\s+Seguran[çc]a)"
)

# O particípio entre o tribunal e o ano ("proferido", "julgado") aparece
# corrompido pela digitalização, e por isso entra como palavra qualquer.
_PADROES = (
    # "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli"
    rf"\b(?:reiterados?\s+)?{_GENERICO}\s+d[oa]\s+{_TRIBUNAL}"
    rf"(?:[\s,]*(?:\w+\s+)?(?:em|{_DE})\s*{_ANO})?"
    rf"(?:[\s,]*{_RELATOR})?",
    # "Reclamação do STF, de 2025, Rel. Min. CRISTIANO ZANIN"
    rf"\b{_RECURSO}\s+d[oa]\s+{_TRIBUNAL}[\s,]*(?:em|{_DE})\s*{_ANO}"
    rf"[\s,]*{_RELATOR}",
    # "Rcl de 2021, Rel. Min. Rosa Weber"
    rf"\b{_RECURSO}\s+(?:em|{_DE})\s*{_ANO}[\s,]*{_RELATOR}",
    # "artigo correspondente do Código de Processo Civil"
    r"\bartigos?\s+correspondentes?\s+d[oa]\s+"
    r"[A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+(?:d[aeo]s?|[A-ZÀ-Ý][\wÀ-ÿ]*)){0,5}",
)

_COMPILADOS = tuple(re.compile(p) for p in _PADROES)


def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Spans (inicio, fim, trecho) das citações sem identificador."""
    candidatos = []
    for padrao in _COMPILADOS:
        for m in padrao.finditer(texto):
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
