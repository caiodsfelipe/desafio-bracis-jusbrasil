"""
Roteamento e decisão de classe, exercitados sem banco e sem modelo.

A resolução recebe candidatos já buscados no acervo, e são as regras sobre
esses candidatos que os testes verificam.
"""

from resolucao import (
    _LIMITE_CABECALHO,
    Candidato,
    _desempatar_por_posicao,
    _um_por_registro,
)


def candidato(id_canonico, posicao, documento_id="doc"):
    return Candidato(
        documento_id=documento_id,
        id_canonico=id_canonico,
        tribunal=None,
        natureza="acordao",
        posicao=posicao,
        texto="",
        ocorrencia=(posicao - 1, posicao + 10),
    )


def test_um_registro_no_cabecalho_responde_pela_citacao():
    candidatos = [candidato(1, 48), candidato(2, 13_707)]
    resolucao = _desempatar_por_posicao(candidatos)
    assert (resolucao.classe, resolucao.id_canonico) == ("real", 1)


def test_numero_so_mencionado_e_citacao_inventada():
    """Nenhum registro traz o número no cabeçalho: ele consta do acervo
    apenas dentro de fundamentações, e nenhum processo responde por ele."""
    candidatos = [candidato(1, 48_213), candidato(2, 54_289)]
    resolucao = _desempatar_por_posicao(candidatos)
    assert (resolucao.classe, resolucao.id_canonico) == ("inventada", None)


def test_copias_do_mesmo_acordao_resolvem_pelo_menor_id():
    """Duas cópias do mesmo acórdão trazem o número na mesma posição e
    nenhum critério textual as separa; a escolha só precisa ser estável."""
    candidatos = [candidato(1_973_691_658, 1_644), candidato(867_328_396, 1_645)]
    resolucao = _desempatar_por_posicao(candidatos)
    assert (resolucao.classe, resolucao.id_canonico) == ("real", 867_328_396)


def test_processos_distintos_no_cabecalho_vao_ao_modelo():
    """Mesmo número, dois processos, ambos autuados: só a espécie do
    recurso decide, e a posição não basta."""
    candidatos = [candidato(1, 30), candidato(2, 74)]
    assert _desempatar_por_posicao(candidatos) is None


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
