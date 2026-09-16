"""
Ablação de regras contra as duas versões do conjunto de referência.

Uma regra que captura o critério do desafio vale o mesmo nas duas versões
publicadas do conjunto: removê-la derruba os dois resultados de modo
semelhante. Uma regra ajustada à amostra vale muito numa e pouco na outra,
porque descreve o que aqueles documentos têm, e não o que a organização
considera citação.

A assimetria é o sinal procurado. Para cada regra desativada, o script mede
a queda em cada base e a diferença entre as duas quedas:

    queda_final  = score_com_tudo(final)    - score_sem_a_regra(final)
    queda_antiga = score_com_tudo(antiga)   - score_sem_a_regra(antiga)
    assimetria   = |queda_final - queda_antiga|

Uma regra geral tem assimetria próxima de zero, qualquer que seja a queda.
Assimetria alta aponta dependência da amostra, e é o que merece reescrita.

Uso:
    python ablacao.py --base-antiga /caminho/para/base_antiga
"""

import argparse
import collections
import contextlib
import csv
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))


# Um padrão que nunca casa preserva o tipo e a interface do original, de
# modo que o pipeline siga o mesmo caminho de código com a regra ausente.
_NUNCA_CASA = re.compile(r"(?!x)x")


@contextlib.contextmanager
def _sem_padrao(modulo, atributo):
    """Desativa um padrão compilado e o devolve ao sair."""
    original = getattr(modulo, atributo)
    setattr(modulo, atributo, _NUNCA_CASA)
    try:
        yield
    finally:
        setattr(modulo, atributo, original)


@contextlib.contextmanager
def _sem_tupla_de_padroes(modulo, atributo, indice):
    """Desativa um dos padrões de uma tupla compilada."""
    original = getattr(modulo, atributo)
    substituta = tuple(
        _NUNCA_CASA if i == indice else p for i, p in enumerate(original)
    )
    setattr(modulo, atributo, substituta)
    try:
        yield
    finally:
        setattr(modulo, atributo, original)


@contextlib.contextmanager
def _sem_filtro(modulo, atributo):
    """Desativa um filtro, fazendo-o responder que nunca se aplica."""
    original = getattr(modulo, atributo)
    setattr(modulo, atributo, lambda *_: False)
    try:
        yield
    finally:
        setattr(modulo, atributo, original)


def _ablacoes():
    """As regras que podem ser desativadas, e como desativar cada uma."""
    import regex_extracao
    import regex_prosa

    return (
        ("citacao com identificador", _sem_padrao, (regex_extracao, "_PADRAO_CITACAO")),
        ("sumula", _sem_padrao, (regex_extracao, "_PADRAO_SUMULA")),
        ("artigo de lei", _sem_padrao, (regex_extracao, "_PADRAO_ARTIGO")),
        ("tema de repercussao", _sem_padrao, (regex_extracao, "_PADRAO_TEMA")),
        (
            "filtro de numero administrativo",
            _sem_filtro,
            (regex_extracao, "_e_numero_administrativo"),
        ),
        (
            "prosa: termo jurisprudencial",
            _sem_tupla_de_padroes,
            (regex_prosa, "_COMPILADOS", 0),
        ),
        (
            "prosa: especie e orgao",
            _sem_tupla_de_padroes,
            (regex_prosa, "_COMPILADOS", 1),
        ),
        (
            "prosa: especie e ano",
            _sem_tupla_de_padroes,
            (regex_prosa, "_COMPILADOS", 2),
        ),
    )


def _carregar_gabarito(caminho):
    with open(caminho, encoding="utf-8-sig") as arquivo:
        por_documento = collections.defaultdict(list)
        for linha in csv.DictReader(arquivo):
            por_documento[linha["documento_id"]].append(linha)
    return por_documento


class _Base:
    """Uma versão do conjunto: acervo, documentos e gabarito."""

    def __init__(self, nome, diretorio, gabarito_csv):
        from indice_normativo import construir_indice

        self.nome = nome
        self.pasta = Path(diretorio)
        self.con = sqlite3.connect(self.pasta / "desafio1_bracis.db")
        self.indice = construir_indice(self.con)
        self.gabarito = _carregar_gabarito(gabarito_csv)

    def pontuar(self):
        import kaggle_metric
        import pandas as pd
        from avaliar import (
            ModeloAusente,
            _celula_da_predicao,
            _celula_do_gabarito,
            prever,
        )

        modelo = ModeloAusente()
        solucao, submissao = [], []
        for documento in sorted(self.gabarito):
            texto = (self.pasta / "txt" / f"{documento}.txt").read_text(
                encoding="utf-8"
            )
            candidatos, resolucoes = prever(self.con, modelo, self.indice, texto)
            solucao.append(
                {
                    "documento_id": documento,
                    "nivel": int(self.gabarito[documento][0]["nivel"]),
                    "Usage": "Public",
                    "citacoes": _celula_do_gabarito(self.gabarito[documento]),
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


# Abaixo desta diferença entre as quedas, a regra vale o mesmo nas duas
# versões e não há sinal de ajuste à amostra.
_ASSIMETRIA_TOLERADA = 0.02


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-antiga", required=True)
    parser.add_argument("--gabarito-antigo", default=None)
    argumentos = parser.parse_args()

    antiga = Path(argumentos.base_antiga)
    gabarito_antigo = argumentos.gabarito_antigo
    if gabarito_antigo is None:
        candidatos = sorted(antiga.glob("goldenset*.csv"))
        if not candidatos:
            raise SystemExit(f"nenhum goldenset em {antiga}")
        gabarito_antigo = candidatos[0]

    bases = (
        _Base("final", RAIZ, RAIZ / "goldenset_offsets.csv"),
        _Base("antiga", antiga, gabarito_antigo),
    )

    referencia = {base.nome: base.pontuar() for base in bases}
    print("com todas as regras")
    for nome, score in referencia.items():
        print(f"  {nome:<8}{score:.6f}")

    print(f"\n{'regra desativada':<34}{'queda final':>13}{'queda antiga':>14}{'assim.':>9}")
    suspeitas = []
    for nome, desativar, alvo in _ablacoes():
        with desativar(*alvo):
            quedas = {b.nome: referencia[b.nome] - b.pontuar() for b in bases}
        assimetria = abs(quedas["final"] - quedas["antiga"])
        marca = " <-" if assimetria > _ASSIMETRIA_TOLERADA else ""
        print(
            f"{nome:<34}{quedas['final']:>13.6f}{quedas['antiga']:>14.6f}"
            f"{assimetria:>9.4f}{marca}"
        )
        if assimetria > _ASSIMETRIA_TOLERADA:
            suspeitas.append((nome, assimetria))

    print()
    if suspeitas:
        print(f"regras com assimetria acima de {_ASSIMETRIA_TOLERADA}:")
        for nome, assimetria in suspeitas:
            print(f"  {nome} ({assimetria:.4f})")
    else:
        print(
            f"nenhuma regra com assimetria acima de {_ASSIMETRIA_TOLERADA}: "
            "todas valem o mesmo nas duas versões"
        )


if __name__ == "__main__":
    raise SystemExit(main())
