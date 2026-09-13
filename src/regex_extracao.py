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

# rejeita match que termina em preposição (de/em) + ano isolado de 4 dígitos
# — sinal de citação em prosa ("proferido em 2024"), não identificador real
_PADRAO_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+\d{4}$", re.IGNORECASE)


def extrair_candidatos(texto: str) -> list[tuple[int, int, str]]:
    """Retorna [(inicio, fim, trecho), ...] para cada citação estruturada
    encontrada por regex. Não decompõe rótulo/identificador — a normalização
    (normalizacao.py) faz isso depois, a partir do span já delimitado."""
    candidatos = []
    for padrao in (_PADRAO_CITACAO, _PADRAO_SUMULA):
        for m in padrao.finditer(texto):
            if _PADRAO_PREPOSICAO_ANO.search(m.group()):
                continue
            candidatos.append((m.start(), m.end(), m.group()))
    return candidatos
