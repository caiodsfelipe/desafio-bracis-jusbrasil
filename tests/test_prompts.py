"""
Registro de prompts e leitura da resposta do modelo.

O contrato que importa é o da fronteira: o pipeline precisa continuar
determinístico diante de qualquer resposta, inclusive fora do formato.
"""
import pytest

from prompt_dono import _indice_da_resposta, montar_opcoes
from prompts import Prompt, registrar
from prompts.escolha_de_registro import VIGENTE as ESCOLHA
from prompts.extracao_em_prosa import VIGENTE as EXTRACAO


@pytest.mark.parametrize("prompt", [ESCOLHA, EXTRACAO])
def test_prompt_vigente_tem_versao_e_nota(prompt):
    assert prompt.versao.startswith("v")
    assert prompt.nota and prompt.texto


def test_registrar_devolve_a_ultima_versao():
    a = Prompt("x", "v1", "a", "primeira")
    b = Prompt("x", "v2", "b", "segunda")
    assert registrar((a, b)) is b


def test_registrar_recusa_familia_vazia():
    with pytest.raises(ValueError):
        registrar(())


@pytest.mark.parametrize(
    "resposta, esperado",
    [("1", 0), ("2", 1), ("Opção 2", 1), (" 2. porque", 1)],
)
def test_escolha_valida(resposta, esperado):
    assert _indice_da_resposta(resposta, 2) == esperado


@pytest.mark.parametrize("resposta", ["", "nenhuma", "9", "-1", "talvez"])
def test_resposta_ilegivel_resolve_pela_primeira_opcao(resposta):
    """A primeira opção é a de identificador mais adiantado, e é a escolha
    mais provável quando o modelo não responde no formato."""
    assert _indice_da_resposta(resposta, 2) == 0


def test_opcoes_sao_numeradas_a_partir_de_um():
    opcoes = montar_opcoes(["AgInt no RECURSO ESPECIAL", "EMBARGOS DE DIVERGÊNCIA"])
    assert opcoes.startswith("1. AgInt")
    assert "\n2. EMBARGOS" in opcoes
