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


@pytest.mark.parametrize(
    "texto",
    [
        "CNPJ 12.345.678/0001-90",
        "o CPF 123.456.789-00",
        "O Protocolo nº 2023.1475691 foi registrado",
        "Advogado inscrito na OAB/MG 241945 subscreve",
        "na Portaria 1.234/2020",
        "o Decreto 9.876/2019",
        "matrícula nº 12345",
        "A condenação foi fixada em R$ 168.772,18.",
    ],
)
def test_numero_administrativo_nao_e_citacao(texto):
    """Cadastro, protocolo, inscrição e ato do Executivo têm a forma de
    citação; o rótulo que os antecede é o que os distingue."""
    assert trechos(texto) == []


@pytest.mark.parametrize(
    "texto",
    [
        "A Reclamação nº 66.516/RO",
        "O Recurso Especial nº 1.377.019/SP",
        "O Agravo Interno na Suspensão de Liminar nº 2.883/MA",
    ],
)
def test_artigo_antes_do_recurso_nao_bloqueia_a_citacao(texto):
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Recurso Especial nº l904603/TO",
        "Recurso Especial nº  l3770l9/ SP",
        "Recl. n° 6G.838/ BA",
    ],
)
def test_letra_no_lugar_do_primeiro_algarismo(texto):
    """A digitalização troca também o primeiro dígito; o número segue
    reconhecível desde que traga dois algarismos verdadeiros."""
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("artigo 1 143 da CLT", "artigo 1 143 da CLT"),
        ("art. 1 105 do Código de Processo Civil", "art. 1 105 do Código de Processo Civil"),
        ("art. 1.134 do CPC", "art. 1.134 do CPC"),
    ],
)
def test_separador_de_milhar_como_espaco(texto, esperado):
    assert esperado in trechos(texto)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Também na Reclamação nº 33.125/SP, o Tribunal", "Reclamação nº 33.125/SP"),
        ("Também no Recurso Especial n° 2.467-.648-RS", "Recurso Especial n° 2.467-.648-RS"),
        ("Ainda na Reclamação nº 66.516/RO", "Reclamação nº 66.516/RO"),
    ],
)
def test_adverbio_de_abertura_fica_fora_do_span(texto, esperado):
    """O advérbio tem forma de nome de recurso, mas introduz a citação em
    vez de fazer parte dela."""
    assert esperado in trechos(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "processo nº TST-RR-79500-16.2009.5.15.0016",
        "processo nº TST-E-RR-173000-49.2008.5.15.0024",
    ],
)
def test_designacao_de_processo_entra_no_span(texto):
    """A palavra que designa o feito antecede o número e integra a
    citação."""
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("art 60 da Lei nº 13.467/2017. O", "art 60 da Lei nº 13.467/2017"),
        ("artigo 172 da Lei nº 9.504/1997. A", "artigo 172 da Lei nº 9.504/1997"),
    ],
)
def test_ponto_final_fica_fora_do_numero_do_diploma(texto, esperado):
    assert esperado in trechos(texto)
