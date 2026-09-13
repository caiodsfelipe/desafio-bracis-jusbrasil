# -*- coding: utf-8 -*-
"""
Verificação de substring: localiza, no texto original, as posições onde um
trecho devolvido pelo LLM realmente aparece (em codepoints Unicode, fim
exclusivo — mesma convenção do goldenset/contrato).

Tolerância permitida: SÓ diferença de espaço em branco/quebra de linha entre
o trecho devolvido e o texto original (o LLM tende a normalizar isso mesmo
quando instruído a copiar literalmente). Qualquer outra diferença — inclusive
uma letra ou dígito trocado — é motivo de rejeição, nunca de tolerância:
o dataset propositalmente injeta ruído de OCR (0↔O, 1↔l, 5↔S, m↔rn) nos
identificadores do nível 2, e um LLM "corrigindo" isso ao copiar produziria
um span que não corresponde ao texto original. Não há como distinguir depois
"o modelo truncou/formatou diferente" de "o modelo corrigiu o OCR", então a
tolerância fica estritamente limitada a whitespace.

Não decide qual ocorrência é a "certa" quando há mais de uma — isso fica a
cargo da etapa de deduplicação/mesclagem, que já vai lidar com sobreposição
de candidatos vindos do regex e do LLM.
"""
import re


def _regex_tolerante_a_espaco(trecho: str) -> re.Pattern:
    """Constrói um padrão que casa `trecho` no texto original permitindo
    que cada sequência de espaço/quebra de linha do trecho corresponda a
    qualquer sequência de espaço/quebra de linha (inclusive diferente) no
    texto original. Tudo que não é espaço é casado literalmente."""
    pedacos = re.split(r'\s+', trecho.strip())
    pedacos_escapados = [re.escape(p) for p in pedacos if p]
    return re.compile(r'\s+'.join(pedacos_escapados))


def localizar_ocorrencias(texto: str, trecho: str) -> list[tuple[int, int]]:
    """Retorna [(inicio, fim), ...] para cada ocorrência de `trecho` em
    `texto`, tolerando apenas diferença de espaço/quebra de linha. Lista
    vazia = LLM alucinou ou alterou o trecho (não existe no texto); o
    candidato deve ser descartado."""
    if not trecho or not trecho.strip():
        return []
    padrao = _regex_tolerante_a_espaco(trecho)
    return [m.span() for m in padrao.finditer(texto)]
