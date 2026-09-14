"""
Roteamento e decisão de classe, exercitados sem banco e sem modelo.

A resolução recebe candidatos já buscados no acervo, e são as regras sobre
esses candidatos que os testes verificam.
"""

import pytest

from resolucao import (
    _LIMITE_CABECALHO,
    CONFIANCA_POR_CAMINHO,
    Candidato,
    _desempatar_por_posicao,
    _um_por_registro,
    resolvido_por,
)

# Espécie nomeada na citação sob teste; a resolução a compara com o que
# aparece ao redor do número em cada registro.
CITACAO = "Reclamação nº 22.357/PE"


def candidato(id_canonico, posicao, documento_id="doc", contexto=""):
    """Candidato com a ocorrência posicionada dentro de um texto sintético,
    para que a leitura da espécie ao redor do número encontre o contexto."""
    enchimento = "x" * max(0, posicao - 1 - len(contexto))
    texto = enchimento + contexto + "0000000"
    return Candidato(
        documento_id=documento_id,
        id_canonico=id_canonico,
        tribunal=None,
        natureza="acordao",
        posicao=posicao,
        texto=texto,
        ocorrencia=(len(enchimento) + len(contexto), len(texto)),
    )


def test_um_registro_no_cabecalho_responde_pela_citacao():
    candidatos = [candidato(1, 48), candidato(2, 13_707)]
    resolucao = _desempatar_por_posicao(candidatos, CITACAO)
    assert (resolucao.classe, resolucao.id_canonico) == ("real", 1)


def test_numero_so_mencionado_em_outra_especie_e_inventada():
    """Nenhum registro traz o número no cabeçalho, e onde ele aparece o
    feito é de outra espécie: nenhum processo responde pela citação."""
    candidatos = [
        candidato(1, 48_213, contexto="Mandado de Segurança deferido. MS "),
        candidato(2, 54_289, contexto="o caso emblemático da Infraero ( MS "),
    ]
    resolucao = _desempatar_por_posicao(candidatos, CITACAO)
    assert (resolucao.classe, resolucao.id_canonico) == ("inventada", None)


def test_copias_do_mesmo_acordao_resolvem_pelo_menor_id():
    """Duas cópias do mesmo acórdão trazem o número na mesma posição e
    nenhum critério textual as separa; a escolha só precisa ser estável."""
    candidatos = [candidato(1_973_691_658, 1_644), candidato(867_328_396, 1_645)]
    resolucao = _desempatar_por_posicao(candidatos, CITACAO)
    assert (resolucao.classe, resolucao.id_canonico) == ("real", 867_328_396)


def test_processos_distintos_no_cabecalho_vao_ao_modelo():
    """Mesmo número, dois processos, ambos autuados: só a espécie do
    recurso decide, e a posição não basta."""
    candidatos = [candidato(1, 30), candidato(2, 74)]
    assert _desempatar_por_posicao(candidatos, CITACAO) is None


def test_limite_do_cabecalho_acomoda_a_autuacao_do_tst():
    """No TST o número do processo aparece por volta de mil e cem
    caracteres, depois do relatório de autuação."""
    assert _LIMITE_CABECALHO > 1_100


def test_um_por_registro_mantem_a_ocorrencia_mais_adiantada():
    candidatos = [candidato(7, 900), candidato(7, 120), candidato(9, 400)]
    assert [(c.id_canonico, c.posicao) for c in _um_por_registro(candidatos)] == [
        (7, 120),
        (9, 400),
    ]


CAMINHOS_DETERMINISTICOS = (
    "normativo",
    "sem_identificador",
    "registro_unico",
    "sem_candidato",
    "cabecalho",
)


@pytest.mark.parametrize("caminho", CAMINHOS_DETERMINISTICOS)
def test_confianca_dos_caminhos_deterministicos(caminho):
    """O bônus mede a distância entre a confiança declarada e o acerto
    efetivo. Estes caminhos acertam tudo no conjunto de referência, e
    rebaixar a confiança abaixo do valor medido custa bônus."""
    assert CONFIANCA_POR_CAMINHO[caminho] == 0.99


@pytest.mark.parametrize("caminho", CAMINHOS_DETERMINISTICOS)
def test_confianca_nao_declara_certeza_absoluta(caminho):
    """Declarar 1,0 e errar custa o dobro: com três predições erradas em
    224, 0,99 rende mais bônus que 1,0."""
    assert CONFIANCA_POR_CAMINHO[caminho] < 1.0


def test_caminhos_dependentes_de_sinal_indireto_declaram_menos():
    """A espécie do recurso e a escolha do modelo são sinais mais frágeis
    que a posição do número no cabeçalho."""
    for caminho in ("especie", "desempate", "so_mencionado"):
        assert CONFIANCA_POR_CAMINHO[caminho] < CONFIANCA_POR_CAMINHO["cabecalho"]


def test_resolucao_carrega_o_caminho_que_a_produziu():
    """O diagnóstico por caminho não deve depender do valor da confiança:
    dois caminhos podem declarar o mesmo valor quando acertam igual."""
    resolucao = resolvido_por("cabecalho", "real", 42)
    assert resolucao.caminho == "cabecalho"
    assert resolucao.confianca == CONFIANCA_POR_CAMINHO["cabecalho"]
    assert tuple(resolucao) == ("real", 42)


def test_numero_presente_na_especie_citada_e_real():
    """O número não está em cabeçalho nenhum, mas aparece transcrito num
    feito da mesma espécie: o processo existe, ainda que o acervo não
    guarde o acórdão que o autuou."""
    candidatos = [
        candidato(
            1,
            4_310,
            contexto="autos de Agravo de Instrumento em Recurso de Revista nº TST-AIRR-",
        ),
        candidato(
            2,
            32_488,
            contexto='Agravo de instrumento não provido". (PROCESSO Nº TST-AIRR-',
        ),
    ]
    resolucao = _desempatar_por_posicao(candidatos, "TST-AgARR-25823-78.2015.5.24.0091")
    assert (resolucao.classe, resolucao.id_canonico) == ("real", 1)
    assert resolucao.caminho == "especie"


def test_citacao_sem_especie_reconhecivel_permanece_inventada():
    candidatos = [candidato(1, 48_213), candidato(2, 54_289)]
    resolucao = _desempatar_por_posicao(candidatos, "nº 22.357")
    assert (resolucao.classe, resolucao.id_canonico) == ("inventada", None)
