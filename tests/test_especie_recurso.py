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


def test_formula_de_autuacao_identifica_o_dono_do_numero():
    """O acórdão apresenta os autos que julga; onde a fórmula falta, o
    número está sendo transcrito de outro feito."""
    from especie_recurso import autua_o_processo

    dono = "x" * 100 + "estes autos de Agravo de Instrumento em Recurso de Revista nº "
    assert autua_o_processo(dono + "TST-AIRR-25823", len(dono))

    citante = "x" * 100 + 'não provido". (PROCESSO Nº '
    assert not autua_o_processo(citante + "TST-AIRR-25823", len(citante))


def test_formula_de_autuacao_em_maiusculas():
    from especie_recurso import autua_o_processo

    texto = "x" * 80 + "VISTOS, RELATADOS E DISCUTIDOS estes autos de RR nº "
    assert autua_o_processo(texto + "123", len(texto))
