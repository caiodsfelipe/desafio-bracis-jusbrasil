"""
Registro de prompts e leitura da resposta do modelo.

O contrato que importa é o da fronteira: o pipeline precisa continuar
determinístico diante de qualquer resposta, inclusive fora do formato.
"""
import hashlib

import pytest

from prompt_dono import NENHUMA, _indice_da_resposta, montar_opcoes
from prompts import Prompt, registrar
from prompts.escolha_de_registro import VIGENTE as ESCOLHA
from prompts.extracao_em_prosa import APOSENTADOS as EXTRACAO_APOSENTADOS


@pytest.mark.parametrize("prompt", [ESCOLHA, *EXTRACAO_APOSENTADOS])
def test_prompt_tem_versao_e_nota(prompt):
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


# Soma de verificação do texto que está em produção desde a submissão que
# marcou 1.00755 na avaliação oficial. Nenhuma avaliação local exercita o
# caminho do modelo, de modo que uma reescrita do prompt muda o resultado
# sem alterar nada que se possa medir aqui. Alterar um destes valores é
# declarar que a mudança é deliberada e que será medida numa submissão.
SOMAS_EM_PRODUCAO = {"escolha_de_registro@v2": "e7240aaff50ed877"}


@pytest.mark.parametrize("prompt", [ESCOLHA])
def test_texto_em_producao_nao_mudou(prompt):
    soma = hashlib.sha256(prompt.texto.encode()).hexdigest()[:16]
    assert soma == SOMAS_EM_PRODUCAO[prompt.identificador], (
        f"o texto de {prompt.identificador} mudou; crie uma versão nova em vez "
        "de editar a que está em produção"
    )


def test_modelo_pode_recusar_todas_as_opcoes():
    """O prompt em produção admite zero como resposta, e o pipeline lê essa
    recusa como citação a processo que não está no acervo."""
    assert "0" in ESCOLHA.texto
    assert _indice_da_resposta("0", 2) == NENHUMA
