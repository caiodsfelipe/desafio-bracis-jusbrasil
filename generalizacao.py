"""
Medida de generalização por validação cruzada entre documentos.

O leaderboard da fase de treino roda sobre os mesmos documentos que servem
de referência aqui, e por isso não distingue um sistema que generaliza de
um que decorou. A classificação final sai de documentos que ninguém viu, o
que torna essa distinção a única coisa que importa.

A medida: separar os documentos em partes, avaliar cada parte com o
pipeline inteiro e comparar com o resultado obtido sobre todos. Uma queda
sistemática ao sair de uma parte para outra indicaria que as regras se
apoiam em traços de documentos específicos.

O teste é honesto no que consegue ser: as regras estruturais foram escritas
lendo estes documentos, e nenhuma validação cruzada desfaz isso. O que ele
mede é se o desempenho depende de *quais* documentos, que é o sintoma
observável de um ajuste excessivo.

Uso:
    python generalizacao.py
    python generalizacao.py --gabarito gabarito_reconstruido.csv
"""

import argparse
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

# Uma parte por documento é o corte mais exigente: cada documento é avaliado
# como se fosse o único do conjunto.
_PARTES_PADRAO = 26


def _avaliar(documentos, gabarito, con, indice, modelo, pasta):
    import kaggle_metric
    import pandas as pd
    from avaliar import _celula_da_predicao, _celula_do_gabarito, prever

    solucao, submissao = [], []
    for documento in sorted(documentos):
        texto = Path(pasta, f"{documento}.txt").read_text(encoding="utf-8")
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
    return kaggle_metric.score(
        pd.DataFrame(solucao), pd.DataFrame(submissao), "documento_id"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acervo", default=str(RAIZ / "desafio1_bracis.db"))
    parser.add_argument("--gabarito", default=str(RAIZ / "goldenset.csv"))
    parser.add_argument("--documentos", default=str(RAIZ / "txt"))
    parser.add_argument("--partes", type=int, default=_PARTES_PADRAO)
    argumentos = parser.parse_args()

    from avaliar import ModeloAusente, carregar_gabarito

    from indice_normativo import construir_indice

    con = sqlite3.connect(argumentos.acervo)
    indice = construir_indice(con)
    gabarito = carregar_gabarito(argumentos.gabarito)
    modelo = ModeloAusente()

    todos = sorted(gabarito)
    referencia = _avaliar(todos, gabarito, con, indice, modelo, argumentos.documentos)
    print(f"conjunto inteiro    {referencia:.6f}   ({len(todos)} documentos)")

    tamanho = max(1, len(todos) // argumentos.partes)
    partes = [todos[i : i + tamanho] for i in range(0, len(todos), tamanho)]
    scores = []
    for parte in partes:
        score = _avaliar(parte, gabarito, con, indice, modelo, argumentos.documentos)
        scores.append((score, parte))

    scores.sort()
    print(f"\npor parte ({len(partes)} partes de até {tamanho} documento)")
    print(f"  pior    {scores[0][0]:.6f}   {' '.join(scores[0][1])}")
    print(f"  mediana {scores[len(scores) // 2][0]:.6f}")
    print(f"  melhor  {scores[-1][0]:.6f}   {' '.join(scores[-1][1])}")

    abaixo = [s for s, _ in scores if s < referencia - 0.01]
    print(f"\npartes abaixo da referência por mais de 0,01: {len(abaixo)} de {len(partes)}")
    for score, parte in scores:
        if score < referencia - 0.01:
            print(f"  {score:.6f}   {' '.join(parte)}")
    if not abaixo:
        print("  nenhuma: o desempenho não depende de quais documentos são avaliados")


if __name__ == "__main__":
    main()
