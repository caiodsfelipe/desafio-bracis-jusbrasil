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
    efetivo. Estes caminhos acertam tudo nas duas versões do conjunto de
    referência, e rebaixar a confiança abaixo do valor medido custa bônus.

    Só o brier exatamente zero leva o bônus a 0,10 cheio: 0,9999 produz
    0,099999999, o score fica em 1,099999999 e o leaderboard, que trunca em
    cinco casas, exibe 1,09999 em vez de 1,10000."""
    assert CONFIANCA_POR_CAMINHO[caminho] == 1.0


def test_bonus_maximo_exige_brier_exatamente_zero():
    """A casa decimal que separa 1,09999 de 1,10000 no leaderboard, medida
    sobre a fórmula do bônus."""
    teto = 0.10
    for confianca, esperado in ((1.0, 0.10), (0.9999, 0.099999999)):
        brier = (confianca - 1) ** 2
        assert teto * (1 - brier) == pytest.approx(esperado, abs=1e-12)
    assert int((1 + 0.099999999) * 100000) / 100000 == 1.09999
    assert int((1 + 0.10) * 100000) / 100000 == 1.10000


def test_caminhos_dependentes_de_sinal_indireto_nao_declaram_confianca():
    """A espécie do recurso e a escolha do modelo são sinais mais frágeis
    que a posição do número no cabeçalho, e o campo é opcional: a média do
    Brier corre só sobre quem declara, de modo que calar retira a citação
    do cálculo sem tirá-la da classificação. Em 75 combinações de fração de
    caminho incerto, taxa de erro e semente, omitir nunca ficou atrás de
    declarar um valor, e chegou a render 0,0157."""
    for caminho in (
        "especie",
        "desempate",
        "so_mencionado",
        "especie_ilegivel",
        "ambiguo",
    ):
        assert CONFIANCA_POR_CAMINHO[caminho] is None


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


def test_sigla_desconhecida_nao_nega_a_existencia_do_processo():
    """Uma sigla fora do vocabulário deixa a citação sem espécie, e o
    silêncio não prova que o processo não existe: errar o link custa menos
    que declarar inventada uma citação real, que é o erro grave."""
    candidatos = [candidato(1, 48_213), candidato(2, 54_289)]
    resolucao = _desempatar_por_posicao(candidatos, "TP 999/DF")
    assert resolucao.classe == "real"
    assert resolucao.caminho == "especie_ilegivel"


def test_especie_conhecida_e_incompativel_nega_a_existencia():
    """Quando a espécie é legível dos dois lados e não bate, o número
    pertence a outro feito e a citação é inventada."""
    candidatos = [
        candidato(1, 48_213, contexto="Mandado de Segurança deferido. MS "),
        candidato(2, 54_289, contexto="o caso emblemático da Infraero ( MS "),
    ]
    resolucao = _desempatar_por_posicao(candidatos, CITACAO)
    assert (resolucao.classe, resolucao.id_canonico) == ("inventada", None)


# A citação pode trazer, além do número do processo, o dia e o mês do
# julgamento e o ano de dois algarismos do diploma. Esses acompanhantes são
# curtos, casam com boa parte do acervo e não identificam processo algum; o
# que os testes abaixo fixam é que eles não decidem a classe da citação.
def _acervo_em_memoria(documentos):
    """Acervo mínimo com o índice FTS5 que a resolução consulta."""
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute(
        "CREATE TABLE documentos"
        " (id INTEGER, documento_id TEXT, tribunal TEXT, natureza TEXT, texto TEXT)"
    )
    con.execute("CREATE VIRTUAL TABLE documentos_fts USING fts5(texto)")
    for id_canonico, texto in documentos:
        con.execute(
            "INSERT INTO documentos (id, documento_id, tribunal, natureza, texto)"
            " VALUES (?, ?, NULL, 'acordao', ?)",
            (id_canonico, f"d{id_canonico}", texto),
        )
        con.execute(
            "INSERT INTO documentos_fts (rowid, texto) VALUES"
            " ((SELECT rowid FROM documentos WHERE id = ?), ?)",
            (id_canonico, texto),
        )
    return con


class _ModeloMudo:
    """Responde a primeira opção, sem carregar pesos."""

    def gerar_lote(self, prompt_sistema, prompts_usuario, **_):
        from llm_qwen import RespostaLLM

        return [RespostaLLM("1") for _ in prompts_usuario]


def _resolver(con, trecho):
    from extracao import CandidatoCitacao
    from resolucao import resolver_citacao

    candidato = CandidatoCitacao(0, len(trecho), trecho, "padrao")
    return resolver_citacao(con, _ModeloMudo(), {}, candidato)


def test_ano_da_citacao_nao_torna_real_um_processo_inventado():
    """O ano é buscado no acervo como o par de tokens "2 024" e casa com o
    sequencial de um acórdão qualquer. Sem descartá-lo, um número que o
    acervo não contém passaria por `real`, com link errado e confiança
    plena, que é o erro que a métrica mais pune."""
    con = _acervo_em_memoria([(10, "RECURSO ESPECIAL Nº 2024005 - RJ " + "x" * 400)])
    resolucao = _resolver(con, "Reclamação 77.777/2.024")
    assert (resolucao.classe, resolucao.id_canonico) == ("inventada", None)


def test_numero_curto_da_data_nao_apaga_a_resposta_do_processo():
    """O dia e o mês casam com boa parte do acervo e são ambíguos por
    definição. Como o número do processo já respondeu, e o acervo não o
    contém, a citação é inventada em vez de incompleta."""
    con = _acervo_em_memoria(
        [(idc, f"Documento {idc} de 07 e 01 no acervo. " + "x" * 200) for idc in range(1, 30)]
    )
    resolucao = _resolver(con, "ADI 9.999.999 (07/01/2021)")
    assert (resolucao.classe, resolucao.caminho) == ("inventada", "sem_candidato")
