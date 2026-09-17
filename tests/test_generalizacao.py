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
    "texto",
    [
        "decisão do STJ de 2020, Rel. Min. Herman Benjamin",
        "aresto do STF de 2019, da relatoria de Luiz Fux",
        "entendimento firmado pelo STJ em 2021",
        "jurisprudência do TST consolidada em 2018",
        "acórdão da Segunda Turma do STF, de 2023, Rel. Min. Gilmar Mendes",
        "precedente da Corte Especial do STJ de 2020",
        "orientação jurisprudencial do TST de 2019",
        "julgado do TRF4 de 2021, Rel. Des. Maria",
    ],
)
def test_julgado_descrito_em_redacao_nova(texto):
    """A citação identifica o julgado pelo órgão e pelo ano ou relator. O
    padrão descreve as peças, e não as combinações observadas."""
    assert _trecho(texto, extrair_em_prosa) == texto


@pytest.mark.parametrize(
    "texto",
    [
        "reiterados precedentes do Superior Tribunal de Justiça",
        "a jurisprudência pacífica desta Corte",
        "o verbete sumular aplicável à espécie",
        "artigo correspondente do Código de Processo Civil",
        "o entendimento sumulado sobre a matéria",
        "a orientação dos tribunais superiores é firme no ponto",
    ],
)
def test_referencia_sem_fonte_especifica_nao_e_citacao(texto):
    """O órgão sozinho aponta um conjunto difuso de julgados, não um
    acórdão determinado, e o gabarito não o trata como citação."""
    assert extrair_em_prosa(texto) == []


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


@pytest.mark.parametrize(
    "texto",
    [
        "julgado do TRF1 proferido em 2020 pela relatoria de João Silva",
        "acórdão do TRT 15 de 2021",
        "julgado do TRE-BA de 2022",
    ],
)
def test_digito_da_sigla_do_orgao_nao_e_identificador(texto):
    """Em "TRF1" e "TRT 15" o número nomeia a região, não o processo, e um
    algarismo solto casa com metade do acervo."""
    from normalizacao import normalizar_identificadores

    assert normalizar_identificadores(texto) == []


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("REsp 1.234.567/SP", ["1.234.567"]),
        ("Rcl 33.132/AC", ["33.132"]),
        ("Súmula 83 do STJ", ["83"]),
        ("TST-AgARR-25823-78.2015.5.24.0091", ["25823-78.2015.5.24.0091"]),
    ],
)
def test_identificador_legitimo_sobrevive_ao_filtro(texto, esperado):
    from normalizacao import normalizar_identificadores

    assert normalizar_identificadores(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "acórdão do TRF3 de 2022, Rel. Des. Ana Costa",
        "julgado do Tribunal Regional Federal da 3ª Região de 2020, Rel. Des. Silva",
        "acórdão proferido pelo TRT da 2ª Região em 2021",
        "aresto do TST de 2018, da lavra do Ministro Vieira",
        "decisão monocrática do STJ de 2020, Rel. Min. Og Fernandes",
        "precedente da Terceira Seção do STJ, de 2019, Rel. Min. Reynaldo",
    ],
)
def test_orgao_nomeado_de_formas_diversas(texto):
    """O regional aparece por sigla ou por extenso, e o relator vem por
    relatoria, por lavra ou pela abreviatura."""
    assert _trecho(texto, extrair_em_prosa) == texto


@pytest.mark.parametrize(
    "texto",
    [
        "ADI de 2021, Rel. Min. Fux",
        "ADPF de 2019, Rel. Min. Barroso",
        "HC de 2020, Rel. Min. Vaz",
        "CC de 2022, Rel. Min. Nancy",
        "RHC de 2020, Rel. Min. Laurita Vaz",
        "EDcl de 2022, Rel. Min. Nancy Andrighi",
    ],
)
def test_especie_substitui_o_tribunal(texto):
    """O gabarito trata "Rcl de 2021, Rel. Min. Rosa Weber" como citação: a
    espécie do recurso situa o julgado quando a corte não é nomeada."""
    assert _trecho(texto, extrair_em_prosa) == texto


_CORPO = (
    "A questão de fundo comporta solução singela e merece análise detida, "
    "conforme se demonstra nas linhas que seguem adiante neste parecer.\n"
    "Veja-se o REsp 6.989.916/RS, que ilustra a orientação dominante."
)


@pytest.mark.parametrize(
    "preambulo",
    [
        "",
        "MEMORIAL\n\nProcesso nº 0252874-23.2020.3.18.6580\n\n",
        "PARECER\n\nAutos nº 9293337-24.2018.7.15.8725\n"
        "Apelante: TRANSPORTES MARAJÓ EIRELI\nApelado: Ministério Público\n\n",
        "PODER JUDICIÁRIO\nTRIBUNAL REGIONAL DO TRABALHO\n"
        "GABINETE DO DESEMBARGADOR\n\nAutos nº 1234567-89.2020.5.02.0001\n"
        "Recorrente: EMPRESA X LTDA\nAdvogado: OAB/SP 193771\n"
        "Protocolo nº 2023.1475691\n\n",
        "SUPERIOR TRIBUNAL DE JUSTIÇA GABINETE DO EXCELENTÍSSIMO SENHOR "
        "MINISTRO RELATOR DA TERCEIRA TURMA\nAutos nº 1234567-89.2020.5.02.0001\n\n",
    ],
)
def test_citacao_sobrevive_a_preambulo_de_qualquer_tamanho(preambulo):
    """O preâmbulo é delimitado pela forma, não pela posição: um
    endereçamento mais enxuto que os observados não pode fazer o corte
    engolir a primeira citação. Medido por posição fixa, um preâmbulo cem
    caracteres mais curto já custava 0,014 do score."""
    from extracao import extrair_todos

    trechos = [o.trecho for o in extrair_todos(preambulo + _CORPO)]
    assert "REsp 6.989.916/RS" in trechos


@pytest.mark.parametrize(
    ("linha", "numero"),
    [
        ("Autos nº 9293337-24.2018.7.15.8725", "9293337"),
        ("Processo nº 0252874-23.2020.3.18.6580", "0252874"),
        ("Protocolo nº 2023.1475691", "2023"),
        ("Advogado: OAB/SP 193771", "193771"),
    ],
)
def test_qualificacao_do_proprio_feito_nao_e_citacao(linha, numero):
    """Os autos do próprio documento, o protocolo e a inscrição do
    advogado têm a forma de citação; ficam no preâmbulo e não são
    extraídos."""
    from extracao import extrair_todos

    trechos = [o.trecho for o in extrair_todos(f"MEMORIAL\n\n{linha}\n\n{_CORPO}")]
    assert not any(numero in t for t in trechos)


@pytest.mark.parametrize(
    "texto",
    [
        "O prazo de 15 dias úteis foi observado.",
        "A multa de 20% sobre o valor é devida.",
        "Julgado em 30 de abril, com juros de 12% ao ano.",
        "A redução de 50% da pena foi concedida.",
        "Servidor com idade de 65 anos.",
        "Turma composta de 5 membros.",
        "Acórdão de 2023, sem outros elementos.",
    ],
)
def test_numero_ligado_por_preposicao_nao_e_citacao(texto):
    """A preposição liga o número à palavra anterior como quantidade, prazo
    ou data: "prazo de 15 dias" não é citação. Nenhuma das 192 citações do
    conjunto de referência termina em preposição seguida de número, e três
    frases dessas num documento custavam 0,105 do score."""
    from extracao import extrair_todos

    corpo = "Trata-se de parecer jurídico elaborado para consulta prévia. " * 8
    assert [o.trecho for o in extrair_todos(corpo + texto)] == []


@pytest.mark.parametrize(
    "texto",
    [
        "Rcl 45678/DF",
        "REsp 1.234.567/SP",
        "AgInt no AREsp 1576933/SP",
        "Súmula 331 do TST",
        "art. 373, I, do CPC",
        "Tema 2.680 da repercussão geral",
        "art. 31 da Lei 8.212/1993",
    ],
)
def test_citacao_sobrevive_ao_filtro_de_preposicao(texto):
    """O identificador não se prende ao nome do recurso por preposição, e a
    regra que descarta a quantidade não pode alcançá-lo."""
    from extracao import extrair_todos

    corpo = "Trata-se de parecer jurídico elaborado para consulta prévia. " * 8
    assert texto in [o.trecho for o in extrair_todos(corpo + texto)]


@pytest.mark.parametrize(
    "verbo",
    ["Transcrevo", "Colaciono", "Reproduzo", "Cito", "Destaco"],
)
def test_verbo_colado_ao_recurso_e_limite_conhecido(verbo):
    """Sem artigo entre o verbo e o nome do recurso, o verbo entra no span:
    "Transcrevo RE 99/SP" rende sobreposição de 0,42 e perde a citação.

    Não há correção sem enumerar verbos, porque a terminação não os separa
    de "Agravo", "Processo" e "Recurso". O caso é artificial em português,
    que pede o artigo, e no corpus de 1014 acórdãos aparece uma vez em
    28.754 trechos: o teste registra o limite em vez de escondê-lo.
    """
    from extracao import extrair_todos

    corpo = "Trata-se de parecer jurídico elaborado para consulta prévia. " * 8
    com_artigo = [o.trecho for o in extrair_todos(f"{corpo}{verbo} o RE 1234/SP.")]
    assert "RE 1234/SP" in com_artigo
