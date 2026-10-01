"""
Saída no formato do contrato de entrada e saída do desafio.

O artefato oficial da solução é um JSON por documento; o `submission.csv`
enviado ao Kaggle sai dele pelo conversor `json_to_submission.py`. Gerar o
JSON, e não apenas o CSV, mantém a solução no formato que a organização
confere na verificação de reprodutibilidade.

O CSV carrega span, classe, link e confiança. O JSON carrega também o
`trecho` e o `tipo`, que o conversor descarta mas o validador local exige.
"""

import json
import re
from pathlib import Path

# O gabarito separa as citações em duas espécies, e o dispositivo de lei é o
# que abre por "art." ou "artigo": o critério reproduz os 192 rótulos do
# conjunto de referência. A súmula conta como jurisprudência, ainda que
# resolva pelo índice normativo.
_ABERTURA_DE_DISPOSITIVO = re.compile(r"\s*[Aa]rt(?:igo)?\b")

TIPO_LEI = "lei"
TIPO_JURISPRUDENCIA = "jurisprudencia"


def tipo_da_citacao(trecho: str) -> str:
    """Espécie da citação: dispositivo de lei ou julgado."""
    if _ABERTURA_DE_DISPOSITIVO.match(trecho):
        return TIPO_LEI
    return TIPO_JURISPRUDENCIA


def documento_em_contrato(documento_id: str, candidatos, resolucoes) -> dict:
    """Documento no formato do contrato, pronto para serialização."""
    citacoes = []
    for candidato, resolucao in zip(candidatos, resolucoes, strict=True):
        citacao = {
            "inicio": candidato.inicio,
            "fim": candidato.fim,
            "trecho": candidato.trecho,
            "tipo": tipo_da_citacao(candidato.trecho),
            "classificacao": resolucao.classe,
        }
        if resolucao.confianca is not None:
            citacao["confianca"] = resolucao.confianca
        if resolucao.id_canonico is not None:
            citacao["resolucao"] = {"id_canonico": str(resolucao.id_canonico)}
        citacoes.append(citacao)
    return {"documento_id": documento_id, "citacoes": citacoes}


def celula_da_predicao(candidatos, resolucoes) -> str:
    """Célula `citacoes` do submission.csv: as citações de um documento,
    separadas por barra vertical, ou "-" quando não há nenhuma.

    O formato vive aqui, junto do JSON, porque os dois descrevem a mesma
    predição: o CSV é o que o conversor da organização produz a partir do
    JSON, e escrevê-lo em dois lugares faria a igualdade entre eles depender
    de duas cópias concordarem à mão.

    A confiança é opcional, e o caminho que não a declara entra como "-":
    omiti-la retira a citação da média do Brier sem tirá-la da
    classificação.
    """
    partes = [
        f"{candidato.inicio},{candidato.fim},{resolucao.classe},"
        f"{resolucao.id_canonico if resolucao.id_canonico else '-'},"
        f"{'-' if resolucao.confianca is None else format(resolucao.confianca, '.4f')}"
        for candidato, resolucao in zip(candidatos, resolucoes, strict=True)
    ]
    return "|".join(partes) or "-"


def gravar(destino: Path, documento_id: str, candidatos, resolucoes) -> Path:
    """Grava o JSON de um documento e devolve o caminho escrito."""
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"{documento_id}.json"
    caminho.write_text(
        json.dumps(
            documento_em_contrato(documento_id, candidatos, resolucoes),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return caminho
