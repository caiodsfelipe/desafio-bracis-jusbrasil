"""
Normalização do identificador.

Os casos cobrem as formas de ruído que a digitalização produz, e não apenas
as presentes no conjunto de referência: o objetivo é que a regra continue
válida diante de uma combinação ainda não vista.
"""
import pytest

from normalizacao import normalizar_identificadores


@pytest.mark.parametrize(
    "trecho, esperado",
    [
        ("REsp 1.234.567/SP", ["1.234.567"]),
        ("AgInt nos EDcl no REsp 2144995/RJ", ["2.144.995"]),
        ("ARR-213-85.2010.5.02.0030", ["213-85.2010.5.02.0030"]),
    ],
)
def test_identificador_limpo(trecho, esperado):
    assert normalizar_identificadores(trecho) == esperado


@pytest.mark.parametrize(
    "trecho, esperado",
    [
        ("REsp l.234.567/SP", ["1.234.567"]),
        ("REsp 1.2S4.567/SP", ["1.254.567"]),
        ("HC 12O.456/RJ", ["120.456"]),
        ("RE 98g.654", ["989.654"]),
        ("Recurso Especial Nº 170076O (SP)", ["1.700.760"]),
    ],
)
def test_letra_no_lugar_do_digito(trecho, esperado):
    assert normalizar_identificadores(trecho) == esperado


@pytest.mark.parametrize(
    "trecho, esperado",
    [
        ("Rec. Esp. No\xa01.880.529\n- SP", ["1.880.529"]),
        ("TST-AgARR-25823-78.2015.5.24.\n0091", ["25823-78.2015.5.24.0091"]),
        ("Rec. Esp. nº  1. 570.531 - CE", ["1.570.531"]),
        ("Rcl 66 516/RO", ["66.516"]),
    ],
)
def test_numero_partido_pela_digitalizacao(trecho, esperado):
    """Espaço, quebra de linha e pontuação repetida entre dígitos pertencem
    ao número; separá-los produziria fragmentos que casam com o acervo
    inteiro."""
    assert normalizar_identificadores(trecho) == esperado


@pytest.mark.parametrize(
    "trecho",
    ["processo 2173718 - SP", "21737l8 - SP", "REsp 1.234.567/SP"],
)
def test_sigla_da_uf_fica_de_fora(trecho):
    (identificador,) = normalizar_identificadores(trecho)
    assert not identificador.endswith(("-", ".", "5", "0")) or identificador[-1].isdigit()
    assert "S" not in identificador and "P" not in identificador


def test_numero_do_cnj_recebe_a_mascara():
    assert normalizar_identificadores("REspe 06003164920206160182") == [
        "0600316-49.2020.6.16.0182"
    ]


def test_ano_de_julgamento_nao_e_identificador():
    assert normalizar_identificadores("julgado do STF proferido em 2024") == []


@pytest.mark.parametrize(
    "trecho, ano, processo",
    [
        ("Petição 45.556/2023", "2.023", "45.556"),
        ("REsp 1.234.567/SP, julgado em 12/03/2024", "2.024", "1.234.567"),
        ("Reclamação 77.777/2.024", "2.024", "77.777"),
        ("ADI 6.524 (07/01/2021)", "2.021", "6.524"),
    ],
)
def test_ano_que_acompanha_o_numero_do_processo_sai(trecho, ano, processo):
    """O ano do julgamento não identifica processo algum, e a preposição
    nem sempre o antecede.

    O FTS5 ignora o separador de milhar e busca "2.024" como o par de
    tokens "2 024", que casa com o sequencial de um acórdão sem relação com
    a citação. Como são poucos os registros atingidos, o número escapa do
    filtro de ambiguidade e faz um processo inventado passar por `real`.

    O dia e o mês continuam na lista: são curtos, casam com boa parte do
    acervo e o filtro de ambiguidade já os neutraliza.
    """
    identificadores = normalizar_identificadores(trecho)
    assert ano not in identificadores
    assert identificadores[0] == processo


def test_ano_sozinho_continua_sendo_identificador():
    """Só há o que contaminar quando o ano acompanha outro número; sozinho
    ele segue como o único identificador disponível."""
    assert normalizar_identificadores("Processo 2024") == ["2.024"]


def test_citacao_sem_numero_nao_produz_identificador():
    assert normalizar_identificadores("precedente do STM, relatoria de Marco Antonio") == []
