"""
Delimitação das citações que descrevem o julgado sem dar seu número.

Metade dos casos usa formas que não aparecem no conjunto de referência. O
padrão descreve as peças da citação (termo jurisprudencial, órgão julgador,
ano, relator) e não as combinações observadas, de modo que uma redação
nova continue reconhecível.
"""
import pytest

from regex_prosa import extrair_candidatos


def trechos(texto):
    return [t for _, _, t in extrair_candidatos(texto)]


@pytest.mark.parametrize(
    "trecho",
    [
        "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli",
        "precedente do STM de 2023, da relatoria de Marco Antonio",
        "acórdão do TSE julgado em 2020 sob relatoria de Edson Fachin",
        "Reclamação do STF, de 2025, Rel. Min. CRISTIANO ZANIN",
        "Rcl de 2021, Rel. Min. Rosa Weber",
        "artigo correspondente do Código de Processo Civil",
    ],
)
def test_moldes_do_conjunto_de_referencia(trecho):
    assert trecho in trechos(trecho)


@pytest.mark.parametrize(
    "trecho",
    [
        "decisão do STJ de 2020, Rel. Min. Herman Benjamin",
        "aresto do STF de 2019, da relatoria de Luiz Fux",
        "entendimento firmado pelo STJ em 2021",
        "jurisprudência do TST consolidada em 2018",
        "precedente da Corte Especial do STJ de 2020",
        "acórdão da Segunda Turma do STF, de 2023, Rel. Min. Gilmar Mendes",
        "orientação jurisprudencial do TST",
        "AgRg de 2020, Rel. Min. Og Fernandes",
        "RMS de 2019, Rel. Min. Sebastião Reis",
        "julgado do TRT 2 de 2022",
        "precedente do TRF4 de 2021, Rel. Des. Maria",
    ],
)
def test_formas_ausentes_do_conjunto_de_referencia(trecho):
    assert trecho in trechos(trecho)


def test_tolera_ruido_no_padrao_e_na_preposicao():
    trecho = "julgado do STF profcrido em 2025 pela relatoria de CRISTIANO\nZANIN"
    assert trecho in trechos(trecho)


def test_texto_sem_citacao_nao_produz_candidato():
    assert trechos("A questão de fundo comporta solução singela.") == []


def test_participio_corrompido_nao_impede_a_citacao():
    trecho = "acórdão do STJ julgadc em 2021 sob relatoria de Assusete Magalhães"
    assert trecho in trechos(trecho)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        (
            "caminham os reiterados\nprecedentes do Superior Tribunal de Justiça.",
            "reiterados\nprecedentes do Superior Tribunal de Justiça",
        ),
        (
            "precedente da Corte Especial do STJ de 2020",
            "precedente da Corte Especial do STJ de 2020",
        ),
    ],
)
def test_borda_da_citacao(texto, esperado):
    """O adjetivo que qualifica o julgado faz parte da citação, e o órgão
    fracionário não encerra o span antes do tribunal."""
    assert esperado in trechos(texto)


def test_termo_jurisprudencial_nao_engole_a_sumula_seguinte():
    """"Corrobora esse entendimento a Súmula 935 do STF" traz uma citação de
    súmula, que o padrão estrutural delimita; o termo em prosa não deve
    absorvê-la."""
    assert trechos("Corrobora esse entendimento a Súmula 935\ndo STF, que") == []



@pytest.mark.parametrize(
    "trecho",
    [
        "jurisprudência pacífica desta Corte",
        "orientação jurisprudencial da Corte Superior",
        "verbete sumular aplicável à espécie",
        "entendimento sumulado sobre a matéria",
        "precedentes desta Casa em situações análogas",
        "precedente firmado em sede de recurso repetitivo",
        "jurisprudência consolidada dos tribunais superiores",
        "dispositivo constitucional invocado na origem",
        "lei que disciplina a prescrição no caso",
        "normas de regência da matéria",
        "recente acórdão da Segunda Turma",
    ],
)
def test_referencia_vaga_e_citacao(trecho):
    """A peça invoca o precedente ou a norma sem nomear número nem tribunal.
    A referência é real, resolve para nada, e o gabarito a classifica como
    incompleta."""
    assert trecho in trechos(trecho)


@pytest.mark.parametrize(
    "trecho",
    [
        "entendirnento sumulado sobre a matéria",
        "jurisprudêneia consolidada dos tribunais superiores",
    ],
)
def test_referencia_vaga_com_ruido_de_digitalizacao(trecho):
    assert trecho in trechos(trecho)


def test_estado_da_jurisprudencia_nao_e_citacao():
    """"A orientação dos tribunais superiores é firme no ponto" afirma que a
    jurisprudência está assentada; não invoca precedente algum."""
    texto = "Cumpre observar que a orientação dos tribunais superiores é firme no ponto."
    assert trechos(texto) == []


def test_formulas_vagas_nao_se_confundem_com_argumentacao():
    """No corpus, cada fórmula vaga é sempre citação, e a fórmula que afirma
    o estado da jurisprudência nunca é. A separação é limpa, sem caso em que
    a mesma redação sirva às duas funções."""
    sempre_citacao = (
        "verbete sumular aplicável à espécie",
        "jurisprudência pacífica desta Corte",
        "orientação jurisprudencial da Corte Superior",
        "entendimento sumulado sobre a matéria",
        "precedente firmado em sede de recurso repetitivo",
        "lei que disciplina a prescrição no caso",
        "dispositivo constitucional invocado na origem",
    )
    for formula in sempre_citacao:
        assert formula in trechos(formula), formula
    assert trechos("a orientação dos tribunais superiores é firme no ponto") == []


@pytest.mark.parametrize(
    "texto, esperado",
    [
        (
            "Rcl de 2025, Rel. Min. CÁRMEN LÚCIA.\n\nIII",
            "Rcl de 2025, Rel. Min. CÁRMEN LÚCIA",
        ),
        (
            "Reclamação do STF, de 2020, Rel. Min. Celso De Mello. Antes de",
            "Reclamação do STF, de 2020, Rel. Min. Celso De Mello",
        ),
        (
            "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli. A",
            "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli",
        ),
    ],
)
def test_nome_do_relator_para_no_fim_da_frase(texto, esperado):
    """O ponto continua o nome quando encerra abreviatura ("Rel.", "Min."),
    e o encerra quando encerra a frase."""
    assert esperado in trechos(texto)


def test_dispositivo_legal_de_regencia_e_citacao():
    """Irmã de "normas de regência da matéria", que o gabarito anota."""
    assert "dispositivo legal de regência" in trechos(
        "A pretensão encontra amparo expresso no dispositivo legal de regência."
    )
