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
