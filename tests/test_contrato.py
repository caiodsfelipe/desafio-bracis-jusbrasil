"""
Cobertura do formato de saída.

O artefato oficial da solução é o JSON por documento, e o CSV enviado ao
Kaggle sai dele pelo conversor da organização. O que estes casos travam é a
correspondência entre os dois: um JSON que o conversor leia diferente do
que o notebook escreve direto separaria a submissão medida da submissão
enviada.
"""

import json

import pytest

from contrato import (
    TIPO_JURISPRUDENCIA,
    TIPO_LEI,
    documento_em_contrato,
    gravar,
    tipo_da_citacao,
)


class _Candidato:
    def __init__(self, inicio, fim, trecho):
        self.inicio = inicio
        self.fim = fim
        self.trecho = trecho


class _Resolucao:
    def __init__(self, classe, id_canonico=None, confianca=None):
        self.classe = classe
        self.id_canonico = id_canonico
        self.confianca = confianca


@pytest.mark.parametrize(
    ("trecho", "esperado"),
    [
        ("art. 373, I, do CPC", TIPO_LEI),
        ("artigo 186 do Código Civil", TIPO_LEI),
        ("art 276 do Código Eleitoral", TIPO_LEI),
        ("Súmula 331 do TST", TIPO_JURISPRUDENCIA),
        ("Rcl 45678/DF", TIPO_JURISPRUDENCIA),
        ("AgInt no AREsp 1576933/SP", TIPO_JURISPRUDENCIA),
        ("julgado do STF proferido em 2024", TIPO_JURISPRUDENCIA),
    ],
)
def test_tipo_separa_dispositivo_de_julgado(trecho, esperado):
    """O gabarito separa as citações em lei e jurisprudência, e o
    dispositivo é o que abre por "art." ou "artigo". A súmula resolve pelo
    índice normativo, mas conta como jurisprudência."""
    assert tipo_da_citacao(trecho) == esperado


def test_citacao_carrega_os_campos_que_o_validador_exige():
    documento = documento_em_contrato(
        "doc",
        [_Candidato(10, 22, "Rcl 45678/DF")],
        [_Resolucao("real", 123, 0.9999)],
    )
    citacao = documento["citacoes"][0]
    assert documento["documento_id"] == "doc"
    assert {"inicio", "fim", "trecho", "tipo", "classificacao"} <= set(citacao)
    assert citacao["resolucao"] == {"id_canonico": "123"}
    assert citacao["confianca"] == 0.9999


def test_confianca_omitida_nao_aparece_no_json():
    """O campo é opcional, e o caminho que não declara confiança fica fora
    da média do Brier: a chave precisa estar ausente, não nula."""
    documento = documento_em_contrato(
        "doc", [_Candidato(0, 5, "Rcl 12")], [_Resolucao("incompleta")]
    )
    citacao = documento["citacoes"][0]
    assert "confianca" not in citacao
    assert "resolucao" not in citacao


def test_json_gravado_e_lido_pelo_conversor_da_organizacao(tmp_path):
    """O conversor lê classificacao, resolucao.id_canonico e confianca; o
    que ele produz é a linha que o notebook escreve direto."""
    from json_to_submission import encode

    candidatos = [_Candidato(10, 22, "Rcl 45678/DF"), _Candidato(30, 49, "art. 5º da CF")]
    resolucoes = [_Resolucao("real", 123, 0.9999), _Resolucao("incompleta")]
    caminho = gravar(tmp_path, "doc", candidatos, resolucoes)
    documento = json.loads(caminho.read_text(encoding="utf-8"))
    assert encode(documento) == "10,22,real,123,0.9999|30,49,incompleta,-,-"


def test_documento_sem_citacoes_vira_traco():
    """O Kaggle rejeita célula vazia."""
    from json_to_submission import encode

    assert encode(documento_em_contrato("doc", [], [])) == "-"
