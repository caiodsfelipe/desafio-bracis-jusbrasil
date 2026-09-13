# -*- coding: utf-8 -*-
"""
Geração automática de dataset de treino para o classificador "documento é
o dono do processo" vs "só cita o processo" — sem anotação manual, usando
o próprio banco de 1016 documentos como fonte de verdade:

  positivo: contexto ao redor do número do PRÓPRIO processo de um acórdão
            (o acórdão É, por definição, o dono do seu próprio número).
  negativo: contexto ao redor de menções desse mesmo número em OUTROS
            documentos do banco (só podem ser citações de terceiro).
"""
import sqlite3

from normalizacao import normalizar_identificadores
from regex_extracao import extrair_candidatos

_JANELA_INICIAL = 600  # onde procurar o número do próprio processo


_REFERENCIA_NORMATIVA = ("súmula", "orientação", " lei ", "lei nº", "lei n.", "artigo", " art.")


def _primeiro_candidato_valido(texto: str) -> str | None:
    for _, _, trecho in extrair_candidatos(texto):
        trecho_lower = trecho.lower()
        if any(marca in trecho_lower for marca in _REFERENCIA_NORMATIVA):
            continue
        idents = normalizar_identificadores(trecho)
        if idents:
            return idents[0]
    return None


def numero_proprio_processo(texto: str) -> str | None:
    """Acha o identificador normalizado mais provável de ser o número do
    próprio processo do documento: PRIMEIRO candidato do regex nos
    primeiros _JANELA_INICIAL caracteres, ignorando súmula/orientação
    jurisprudencial (referências citadas na ementa) — não o de maior
    quantidade de dígitos (testado e descartado: o cabeçalho às vezes cita
    o processo de origem, ex. "RELATOR DO PROCESSO Nº 5097324-27.2023...",
    que tem mais dígitos que o número da própria ação, mas vem DEPOIS
    dele no texto).

    Se nada for encontrado na janela inicial, tenta no texto inteiro —
    cobre o formato do TST, cujo cabeçalho começa com ementa/tese jurídica
    extensa e só identifica o processo bem mais adiante (visto: posição
    30000+ em alguns casos)."""
    return _primeiro_candidato_valido(texto[:_JANELA_INICIAL]) or _primeiro_candidato_valido(texto)
