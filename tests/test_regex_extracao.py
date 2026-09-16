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
        "DJe de 14/3/2024",
        "Publicado no DJe em 5/12/2003",
        "DEJT 03/02/2012",
        "DJ de 3/6/1994",
        "Consta do Evento 17",
        "ID 61582938",
        "Conforme fls. 45",
        "o doc. 12 juntado",
        "mov. 88 dos autos",
    ],
)
def test_publicacao_e_referencia_de_autos_nao_sao_citacao(texto):
    """O diário que publicou o acórdão e a peça numerada dentro dos autos
    têm a forma de identificador sem apontar julgado algum. Nenhum registro
    do acervo os contém, e sem este filtro a resolução os daria por
    inventados com alta confiança."""
    assert trechos(texto) == []


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Rcl 45678/DF, Rel. Min. Fulano, DJe de 14/3/2024", "Rcl 45678/DF"),
        ("REsp 1.234.567/SP, DJe 21/9/2023", "REsp 1.234.567/SP"),
        ("AgInt no AREsp 998877/RJ (DEJT 03/02/2012)", "AgInt no AREsp 998877/RJ"),
    ],
)
def test_publicacao_nao_apaga_a_citacao_que_acompanha(texto, esperado):
    """A data de publicação acompanha o acórdão citado: o julgado continua
    sendo citação, e só o veículo fica de fora."""
    assert esperado in trechos(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "art. 31 da Lei 8.212/1993",
        "art. 39 da Lei n.º 8.177/1991",
        "art. 73, § 50, da Lei no 9.504/97",
        "art. 1º da LC nº 64/90",
        "art. 18, II, h, da LC no 75/93",
        "artigo 3º, I, da LC-108/2001",
        "art. 51 do Decreto-Lei nº 3.688/1941",
        "art. 2º do Decreto-lei 491",
        "art. 4º do Decreto- Lei 4.657/42",
        "art. 146 do Decreto n.º 99.244/90",
        "art. 75 da Lei Complementar nº 64/1990",
    ],
)
def test_numero_do_diploma_entra_no_span(texto):
    """O número identifica o diploma: sem ele "art. 31 da Lei" não aponta
    norma alguma, e a resolução dá por inventada uma citação real. O
    indicador de número é dispensável e aparece em várias grafias, de modo
    que o span não pode depender dele para alcançar o número."""
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "art. 14, do Decreto 27.427/00",
        "artigo 12 do Decreto-lei nº 509/69",
    ],
)
def test_diploma_invocado_por_artigo_nao_e_ato_administrativo(texto):
    """O decreto citado sozinho é ato do Executivo; invocado por um artigo,
    é o diploma que carrega a norma. O artigo à frente separa os dois."""
    assert texto in trechos(texto)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("A Reclamação nº 66.516/RO", "Reclamação nº 66.516/RO"),
        ("O Recurso Especial nº 1.377.019/SP", "Recurso Especial nº 1.377.019/SP"),
        (
            "O Agravo Interno na Suspensão de Liminar nº 2.883/MA",
            "Agravo Interno na Suspensão de Liminar nº 2.883/MA",
        ),
        ("Os EDcl no REsp 1.234.567/SP", "EDcl no REsp 1.234.567/SP"),
    ],
)
def test_artigo_antes_do_recurso_fica_fora_do_span(texto, esperado):
    """O artigo definido antecede o nome do recurso sem compô-lo: em 121 das
    192 citações do conjunto de referência há um artigo colado ao span, e
    nenhuma o inclui. Em início de período ele vem em maiúscula, e sem essa
    distinção entraria na citação."""
    assert esperado in trechos(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Conforme Rcl 45678/DF, a tese se firmou.",
        "Registre-se RE 1234/SP como precedente.",
        "Evidentemente HC 321/BA se aplica.",
        "Todavia AI 87/RS foi rejeitado.",
    ],
)
def test_palavra_que_abre_o_periodo_fica_fora_do_span(texto):
    """O articulador, o verbo com pronome e o advérbio em -mente introduzem a
    citação sem pertencer a ela. Em identificador curto o excedente derruba a
    sobreposição abaixo do limite de 0,5 e a citação é contada como perdida."""
    assert trechos(texto)
    assert all(not t[0].islower() and " " in t for t in trechos(texto))
    assert not any(
        t.startswith(p)
        for t in trechos(texto)
        for p in ("Conforme", "Registre-se", "Evidentemente", "Todavia")
    )


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
