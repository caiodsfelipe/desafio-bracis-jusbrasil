"""
Cobertura de formas que não aparecem no conjunto de referência.

A classificação final sai de documentos que ninguém viu, e o leaderboard da
fase de treino não distingue um sistema que generaliza de um que decorou.
Estes casos foram escritos para exercitar formas plausíveis e ausentes dos
26 documentos distribuídos: uma queda aqui é o sintoma de que uma regra se
apoia em traços de documentos específicos.
"""

import pytest

from especie_recurso import familia
from indice_normativo import eh_citacao_normativa
from regex_extracao import extrair_candidatos as extrair_com_identificador
from regex_prosa import extrair_candidatos as extrair_em_prosa


def _trecho(texto, extrair):
    achados = extrair(texto)
    return achados[0][2] if achados else None


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("a jurisprudência pacífica do Tribunal", "jurisprudência pacífica do Tribunal"),
        ("o entendimento consolidado desta Corte", "entendimento consolidado desta Corte"),
        ("a orientação sumulada da Corte Superior", "orientação sumulada da Corte Superior"),
        ("o precedente vinculante sobre a matéria", "precedente vinculante sobre a matéria"),
        ("a súmula aplicável à espécie", "súmula aplicável à espécie"),
        ("a tese firmada em repercussão geral", "tese firmada em repercussão geral"),
        ("o enunciado sumular pertinente", "enunciado sumular pertinente"),
        ("os precedentes reiterados desta Casa", "precedentes reiterados desta Casa"),
        ("o entendimento firmado pela Corte", "entendimento firmado pela Corte"),
        ("a norma de regência aplicável", "norma de regência aplicável"),
        ("o dispositivo legal invocado na origem", "dispositivo legal invocado na origem"),
        ("a lei que rege a matéria", "lei que rege a matéria"),
        ("o acórdão da Terceira Turma", "acórdão da Terceira Turma"),
        (
            "a orientação uniforme das instâncias superiores",
            "orientação uniforme das instâncias superiores",
        ),
    ],
)
def test_referencia_vaga_em_redacao_nova(texto, esperado):
    """A fórmula tem peças que variam de forma independente, e o padrão
    descreve as peças e não as combinações observadas."""
    assert _trecho(texto, extrair_em_prosa) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "julgado do TRF1 de 2020",
        "precedente do TJSP de 2019",
        "acórdão do TRT 15 de 2021",
        "julgado do TRE-BA de 2022",
        "decisão do TJMG de 2021",
    ],
)
def test_tribunal_ausente_do_conjunto_de_referencia(texto):
    assert _trecho(texto, extrair_em_prosa) == texto


@pytest.mark.parametrize(
    "texto",
    [
        "ADI 5.678",
        "ADPF 442",
        "CC 178.901/MG",
        "Pet 9.876/DF",
        "AgRg no AREsp 1.234.567/SP",
        "EREsp 1.111.222/RJ",
    ],
)
def test_especie_de_recurso_ausente_do_conjunto_de_referencia(texto):
    """O identificador precisa ser delimitado mesmo quando a sigla não está
    no vocabulário de espécies."""
    assert texto in [t for _, _, t in extrair_com_identificador(texto)]


@pytest.mark.parametrize(
    "texto",
    [
        "art. 5º do Código Penal",
        "artigo 10 da Lei de Introdução",
        "art. 20 do Código Tributário Nacional",
        "art. 3º da Lei Maria da Penha",
    ],
)
def test_diploma_ausente_do_acervo_segue_sendo_citacao_normativa(texto):
    """O diploma que o acervo não guarda não resolve para registro algum, e
    a citação é inventada; o que não pode é deixar de ser reconhecida como
    citação normativa e ir parar na busca de acórdãos."""
    assert eh_citacao_normativa(texto)


@pytest.mark.parametrize(
    "texto, esperada",
    [
        ("art. 186 do Codigo Civil de 2002", "codigo_civil"),
        ("artigo 186 do diploma civil", "codigo_civil"),
        ("art. 896 da Consolidação", "clt"),
        ("art. 5º da Constituicao", "constituicao"),
    ],
)
def test_diploma_reconhecido_sem_acento_ou_por_apelido(texto, esperada):
    from indice_normativo import _diploma_da_citacao

    assert _diploma_da_citacao(texto) == esperada


def test_sigla_fora_do_vocabulario_nao_tem_familia():
    """A ausência é aceitável; o que a resolução não pode fazer é tratá-la
    como prova de que o processo não existe."""
    assert familia("TP 999") is None
