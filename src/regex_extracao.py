# -*- coding: utf-8 -*-
"""
Extração de citações de jurisprudência por regex estrutural. Roda em
PARALELO com o extrator via LLM (ver prompt_extracao.py) — nenhum dos dois
decide o território do outro; a mesclagem/deduplicação acontece depois.

Cobertura medida contra o goldenset: 111/164 citações de jurisprudência com
identificador numérico casam o span inteiro. Os ~53 casos restantes (prosa
livre sem número, e formatos pontuais como Súmula abreviada "Súm.", número
com letra disfarçada de OCR no meio, "processo nº" minúsculo antes de sigla
com hífen) ficam a cargo do extrator via LLM — decisão deliberada de não
perseguir cobertura de 100% via regex: cada correção adicional cobre menos
casos e adiciona mais risco de regressão (ver histórico da sessão). Regex
puro não é o padrão de indústria para NER robusto a variação de formato;
aqui ele serve como primeira camada barata e determinística para o grosso
dos casos estruturados, não como solução única.
"""
import re

_CONECTORES = r"(?:em|no|na|nos|nas|de|da|do|das|dos)"
# "N" sozinho (sem mais letras) seguido de º/° pertence ao conector do
# número ("Nº"), não é uma palavra maiúscula do rótulo — sem essa exclusão,
# o token consome só o "N" e deixa o "º" sobrando solto, quebrando o
# reconhecimento do conector logo depois (bug encontrado ao rodar o regex
# contra o cabeçalho real dos documentos do banco, não só os .txt de teste).
_TOKEN_MAIUSCULO = r"(?!N[º°](?!\w))[A-ZÀ-Ý][A-Za-zÀ-ÿ.\-]*"
_CONECTOR_NUMERO = r"(?:[nN][º°o.]\s*)?"
_IDENTIFICADOR = r"[\d.\-/:°ºnN() \n\xa0]*\d"
_SUFIXO_UF = r"(?:\s*[-/–(]\s*[A-Z]{2}\)?)?"

_PADRAO_CITACAO = re.compile(
    rf"{_TOKEN_MAIUSCULO}(?:\s+(?:{_TOKEN_MAIUSCULO}|{_CONECTORES})){{0,12}}"
    rf"\s*{_CONECTOR_NUMERO}\d{_IDENTIFICADOR}{_SUFIXO_UF}"
)

_PADRAO_SUMULA = re.compile(
    r"S[uú]mula(?:\s+Vinculante)?\s+\d+(?:\s+d[oa]\s+[A-ZÀ-Ý]+)?",
    re.IGNORECASE,
)

# Citação de dispositivo de lei: "art. 373, I, do CPC", "artigo 7º, XXIX, da
# Constituição Federal", "art. 1º, I, 'g', da Lei Complementar nº 64/1990".
# Estrutura: art/artigo + número (com ordinal, ponto de milhar) + eventuais
# incisos/alíneas/parágrafos + preposição + nome do diploma (sigla em caixa
# alta, ou nome por extenso iniciado em maiúscula, podendo ter "nº 9.504/1997").
#
# Vale um padrão próprio porque o diploma é parte da identidade da citação
# (art. 290 é real no CPM e inventado na Constituição) e o padrão geral não
# chega até ele: para no número, deixando o span curto demais para o IoU.
_INCISOS = r"(?:\s*,\s*(?:[IVXLC]+|[a-z]|§\s*\d+[º°]?(?:-[A-Z])?|'[a-z]'|\"[a-z]\"))*"
# `\s` (não " ") entre as palavras: o nome do diploma pode ter quebra de
# linha no meio ("Código\nde Processo Penal"). A primeira palavra tem de ser
# maiúscula ou sigla — depois dela conectores minúsculos são aceitos, o que
# cobre "Código de Defesa do Consumidor".
_PALAVRA_DIPLOMA = r"(?:[A-ZÀ-Ý][a-zà-ÿ]+|d[aeo]s?|e)"
_DIPLOMA = (
    r"(?:[A-ZÀ-Ý]{2,}"                                   # sigla: CPC, CLT, CDC
    rf"|[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+{_PALAVRA_DIPLOMA}){{0,5}}"  # ou nome por extenso
    r"(?:\s*n[º°.]?\s*[\d./-]+)?)"                       # e eventual "nº 9.504/1997"
)
# sem re.IGNORECASE: a distinção de caixa em _DIPLOMA é o que separa o nome
# do diploma ("Código de Defesa do Consumidor") do texto comum que o segue
_PADRAO_ARTIGO = re.compile(
    rf"\b[Aa]rt(?:igo)?\.?\s*\d{{1,3}}(?:\.\d{{3}})*[º°]?{_INCISOS}"
    rf"\s*,?\s*d[aeo]s?\s+{_DIPLOMA}"
)

# rejeita match que termina em preposição (de/em) + ano isolado de 4 dígitos
# — sinal de citação em prosa ("proferido em 2024"), não identificador real
_PADRAO_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+\d{4}$", re.IGNORECASE)


def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Retorna [(inicio, fim, trecho), ...] para cada citação estruturada
    encontrada por regex. Não decompõe rótulo/identificador — a normalização
    (normalizacao.py) faz isso depois, a partir do span já delimitado."""
    candidatos = []
    for padrao in (_PADRAO_CITACAO, _PADRAO_SUMULA, _PADRAO_ARTIGO):
        for m in padrao.finditer(texto):
            if _PADRAO_PREPOSICAO_ANO.search(m.group()):
                continue
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
