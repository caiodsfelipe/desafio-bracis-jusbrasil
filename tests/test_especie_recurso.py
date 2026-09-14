"""
Leitura da espécie do recurso.

Um mesmo número percorre várias espécies ao longo da tramitação, e as que
pertencem à mesma família são o mesmo processo em fases distintas. Espécies
de famílias diferentes com o mesmo número são feitos sem relação.
"""

import pytest

from especie_recurso import familia, familia_da_ocorrencia


@pytest.mark.parametrize(
    "texto, esperada",
    [
        ("Reclamação nº 22.357/PE", "reclamacao"),
        ("TST-AgARR-25823-78.2015.5.24.0091", "revista"),
        ("AgInt no Recurso Especial nº 1.597.443", "especial"),
        ("Mandado de Segurança deferido. (MS 22357", "mandado"),
        ("RHC 123.456/SP", "habeas"),
        ("Apelação nº 4.321/RS", "apelacao"),
    ],
)
def test_familia_nomeada(texto, esperada):
    assert familia(texto) == esperada


@pytest.mark.parametrize(
    "texto",
    ["processo nº 1.234.567", "o julgado invocado", "nº 22.357"],
)
def test_sem_especie_reconhecivel(texto):
    assert familia(texto) is None


def test_agravo_de_instrumento_e_revista_sao_a_mesma_familia():
    """O agravo de instrumento em recurso de revista e o recurso de revista
    com agravo tramitam com o mesmo número."""
    assert familia("TST-AIRR-25823") == familia("TST-AgARR-25823")


def test_reclamacao_e_mandado_de_seguranca_sao_familias_distintas():
    assert familia("Reclamação nº 22.357") != familia("MS 22.357")


def test_familia_lida_ao_redor_da_ocorrencia():
    texto = (
        "x" * 200
        + "estes autos de Agravo de Instrumento em Recurso de Revista nº TST-AIRR-25823"
    )
    assert familia_da_ocorrencia(texto, len(texto) - 5) == "revista"


def test_nome_por_extenso_decide_antes_da_sigla():
    """O acórdão que se anuncia como mandado de segurança traz a sigla MS
    adiante; o nome por extenso é o que vale."""
    assert familia("Mandado de Segurança deferido. (MS 22357, Rel.") == "mandado"


@pytest.mark.parametrize(
    "cabecalho, citacao, esperado",
    [
        ("A C Ó R D Ã O I. AGRAVO DA RECLAMANTE. RECURSO DE REVISTA COM AGRAVO.",
         "TST-AgARR-25823-78.2015.5.24.0091", True),
        ("A C Ó R D Ã O AGRAVO DE INSTRUMENTO EM RECURSO DE REVISTA REGIDO PELA LEI",
         "TST-AgARR-25823-78.2015.5.24.0091", False),
        ("AgInt no RECURSO ESPECIAL Nº 1.597.443 - PR", "AgInt no REsp 1.597.443", True),
        ("AgInt nosEMBARGOS DE DIVERGÊNCIA EM RESP Nº 1597443",
         "AgInt no REsp 1.597.443", False),
    ],
)
def test_cabecalho_declara_a_especie_citada(cabecalho, citacao, esperado):
    """O acórdão anuncia no cabeçalho a espécie que julga, e é isso que
    separa dois feitos que tramitam com o mesmo número."""
    from especie_recurso import declara_a_especie_citada

    assert declara_a_especie_citada(cabecalho, citacao) is esperado


def test_citacao_sem_sigla_nao_declara_especie():
    """Sem sigla na citação não há o que casar, e a ausência de sinal não
    deve decidir sozinha."""
    from especie_recurso import declara_a_especie_citada

    assert declara_a_especie_citada("RECURSO ESPECIAL Nº 1.234", "processo nº 1.234") is False
