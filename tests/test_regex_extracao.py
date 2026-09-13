"""
Delimitação das citações que trazem identificador.

Os casos incluem espécies de recurso ausentes do conjunto de referência,
porque o padrão descreve a forma da citação e não deve depender de uma
lista fechada de siglas.
"""
import pytest

from regex_extracao import extrair_candidatos


def trechos(texto):
    return [t for _, _, t in extrair_candidatos(texto)]


@pytest.mark.parametrize(
    "trecho",
    [
        "HC 123.456/SP",
        "RE 987.654/RJ",
        "ADI 5.678",
        "MS 36.123/DF",
        "AREsp 2.345.678/BA",
        "Pet 9.876/DF",
        "Reclamação nº 66.516/RO",
        "EDcl no AgInt no Recurso Especial nº 1.597.443 - PR",
    ],
)
def test_especies_de_recurso(trecho):
    assert trecho in trechos(trecho)


def test_nome_do_recurso_ligado_por_conjuncao():
    texto = "Agravo Interno na Suspensão\nde Liminar e de Sentença nº 2.883/MA"
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    "trecho",
    ["Súmula 83 do STJ", "Súmula Vinculante nº 37", "5úmula 211 do STJ"],
)
def test_sumula_inclusive_com_ruido(trecho):
    assert trecho in trechos(trecho)


def test_tema_de_repercussao_geral():
    assert "Temã 2.680 da repercussão geral" in trechos(
        "o\nTemã 2.680 da repercussão geral, que reconhece"
    )


def test_artigo_alcanca_o_diploma():
    assert "art. 373, I, do CPC" in trechos("nos termos do art. 373, I, do CPC.")


def test_letra_no_numero_nao_engole_a_uf():
    assert "Recl. n° 6G.838/ BA" in trechos("respaldo na Recl. n° 6G.838/ BA, precedente")


@pytest.mark.parametrize("texto", ["DO5", "DA C0", "Publique-se. Intimem-se.\n\n5"])
def test_digito_solto_nao_e_citacao(texto):
    """Uma letra que a digitalização deixou parecida com dígito não forma
    identificador sozinha."""
    assert trechos(texto) == []
