"""
Avaliação contra uma base diferente da que está instalada.

A organização publicou duas versões do dataset, e a diferença entre elas é
a melhor prova de generalização disponível: um sistema ajustado a uma
versão pontua mal na outra, e um que capturou o critério pontua bem nas
duas.

A solução marca 1,081909 na base anterior e 1,099978 na final: pontuar bem
nas duas é o sinal de que a regra acompanha o critério, e não a amostra.

Uso:
    python contraprova.py /caminho/para/outra/base
    python contraprova.py /caminho/para/outra/base --gabarito goldenset.csv
"""

import argparse
import collections
import csv
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))


def _carregar(caminho):
    # O gabarito final traz marca de ordem de bytes; o anterior, não.
    with open(caminho, encoding="utf-8-sig") as arquivo:
        por_documento = collections.defaultdict(list)
        for linha in csv.DictReader(arquivo):
            por_documento[linha["documento_id"]].append(linha)
    return por_documento


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="diretório com desafio1_bracis.db e txt/")
    parser.add_argument("--gabarito", default=None, help="padrão: o da base")
    argumentos = parser.parse_args()

    import kaggle_metric
    import pandas as pd
    from avaliar import ModeloAusente, _celula_da_predicao, _celula_do_gabarito, prever

    from indice_normativo import construir_indice

    base = Path(argumentos.base)
    gabarito_csv = argumentos.gabarito
    if gabarito_csv is None:
        candidatos = sorted(base.glob("goldenset*.csv"))
        if not candidatos:
            raise SystemExit(f"nenhum goldenset em {base}")
        gabarito_csv = candidatos[0]

    con = sqlite3.connect(base / "desafio1_bracis.db")
    indice = construir_indice(con)
    gabarito = _carregar(gabarito_csv)
    modelo = ModeloAusente()

    solucao, submissao = [], []
    for documento in sorted(gabarito):
        texto = (base / "txt" / f"{documento}.txt").read_text(encoding="utf-8")
        candidatos, resolucoes = prever(con, modelo, indice, texto)
        solucao.append(
            {
                "documento_id": documento,
                "nivel": int(gabarito[documento][0]["nivel"]),
                "Usage": "Public",
                "citacoes": _celula_do_gabarito(gabarito[documento]),
            }
        )
        submissao.append(
            {
                "documento_id": documento,
                "citacoes": _celula_da_predicao(candidatos, resolucoes),
            }
        )
    score = kaggle_metric.score(
        pd.DataFrame(solucao), pd.DataFrame(submissao), "documento_id"
    )
    total = sum(len(v) for v in gabarito.values())
    print(f"base      {base}")
    print(f"gabarito  {gabarito_csv} ({total} citações)")
    print(f"score     {score:.6f}")


if __name__ == "__main__":
    raise SystemExit(main())
