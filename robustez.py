"""
Robustez do pipeline sob perturbação dos documentos.

O conjunto de avaliação é cego, e o que ele traz de ruído não está no
conjunto de referência. Este script reaplica a métrica sobre versões
perturbadas dos mesmos documentos, para medir quanto o resultado depende da
grafia exata observada.

As perturbações preservam o comprimento do texto, de modo que os spans do
gabarito continuem válidos.

Uso:
    python robustez.py
"""
import argparse
import collections
import csv
import random
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

SEMENTE = 0
FRACAO_DE_RUIDO = 0.02
# Algarismos e as letras por que a digitalização os troca.
TROCA_DE_DIGITALIZACAO = {"0": "O", "1": "l", "5": "S", "6": "G", "9": "g"}


def sem_alteracao(texto):
    return texto


def ruido_de_digitalizacao(texto):
    """Troca por letra uma fração dos algarismos, como faz um OCR ruim."""
    sorteio = random.Random(SEMENTE)
    return "".join(
        TROCA_DE_DIGITALIZACAO[c]
        if c in TROCA_DE_DIGITALIZACAO and sorteio.random() < FRACAO_DE_RUIDO
        else c
        for c in texto
    )


def milhar_como_espaco(texto):
    """O ponto que separa milhares chega como espaço."""
    return re.sub(r"(?<=\d)\.(?=\d{3}\b)", " ", texto)


def ordinal_alternativo(texto):
    """O indicador de número aparece com o outro sinal de grau."""
    return texto.replace("nº", "n°").replace("Nº", "N°")


def travessao_no_lugar_do_hifen(texto):
    return texto.replace(" - ", " – ")


PERTURBACOES = (
    ("original", sem_alteracao),
    ("ruido de digitalizacao 2%", ruido_de_digitalizacao),
    ("milhar como espaco", milhar_como_espaco),
    ("indicador de numero alternativo", ordinal_alternativo),
    ("travessao no lugar do hifen", travessao_no_lugar_do_hifen),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acervo", default=str(RAIZ / "desafio1_bracis.db"))
    parser.add_argument("--gabarito", default=str(RAIZ / "goldenset_offsets.csv"))
    parser.add_argument("--documentos", default=str(RAIZ / "txt"))
    argumentos = parser.parse_args()

    import kaggle_metric
    import pandas as pd
    from avaliar import ModeloAusente, _celula_da_predicao, _celula_do_gabarito, prever

    from indice_normativo import construir_indice

    con = sqlite3.connect(argumentos.acervo)
    indice = construir_indice(con)
    gabarito = collections.defaultdict(list)
    with open(argumentos.gabarito, encoding="utf-8-sig") as arquivo:
        for linha in csv.DictReader(arquivo):
            gabarito[linha["documento_id"]].append(linha)

    solucao = pd.DataFrame(
        [
            {
                "documento_id": documento,
                "nivel": int(citacoes[0]["nivel"]),
                "Usage": "Public",
                "citacoes": _celula_do_gabarito(citacoes),
            }
            for documento, citacoes in sorted(gabarito.items())
        ]
    )

    for nome, perturbar in PERTURBACOES:
        modelo = ModeloAusente()
        submissao = []
        for documento in sorted(gabarito):
            texto = Path(argumentos.documentos, f"{documento}.txt").read_text(
                encoding="utf-8"
            )
            candidatos, resolucoes = prever(con, modelo, indice, perturbar(texto))
            submissao.append(
                {
                    "documento_id": documento,
                    "citacoes": _celula_da_predicao(candidatos, resolucoes),
                }
            )
        score = kaggle_metric.score(
            solucao.copy(), pd.DataFrame(submissao), "documento_id"
        )
        print(f"{nome:<34}{score:.6f}")


if __name__ == "__main__":
    main()
