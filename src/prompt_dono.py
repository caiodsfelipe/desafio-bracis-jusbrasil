"""
Prompt que escolhe, entre os registros do acervo que trazem o mesmo número,
aquele a que a citação se refere.

A pergunta só é feita quando a posição do identificador não decide: vários
processos foram autuados com o mesmo número e diferem apenas na espécie de
recurso. A resposta é o índice de uma das opções apresentadas, e o modelo
não produz nem localiza texto, apenas escolhe entre alternativas já
delimitadas.
"""
from prompts.escolha_de_registro import VIGENTE

PROMPT_SISTEMA = VIGENTE.texto

PROMPT_USUARIO_TEMPLATE = """Citação encontrada na peça:

{citacao}

Opções do acervo:

{opcoes}

Qual opção corresponde à citação?"""

_CARACTERES_DE_CABECALHO = 200


def montar_opcoes(cabecalhos: list[str]) -> str:
    """Lista numerada a partir de 1, com o início de cada acórdão, que é onde
    a espécie do recurso e as partes aparecem."""
    return "\n".join(
        f"{indice}. {' '.join(texto[:_CARACTERES_DE_CABECALHO].split())}"
        for indice, texto in enumerate(cabecalhos, start=1)
    )


NENHUMA = -1


def _indice_da_resposta(resposta: str, total: int) -> int:
    """Índice 0-based lido da resposta, ou NENHUMA quando o modelo recusa
    todas as opções. Uma resposta ilegível resolve pela primeira opção, que
    é a de identificador mais adiantado."""
    digitos = ""
    for caractere in resposta.strip():
        if caractere.isdigit():
            digitos += caractere
        elif digitos:
            break
    if not digitos:
        return 0
    escolha = int(digitos) - 1
    if escolha == NENHUMA:
        return NENHUMA
    return escolha if 0 <= escolha < total else 0


def escolher_registro_lote(qwen, disputas: list[tuple[str, list[str]]]) -> list[int]:
    """Índice do registro escolhido para cada disputa (citação, cabeçalhos),
    numa única passada pela GPU."""
    if not disputas:
        return []
    prompts = [
        PROMPT_USUARIO_TEMPLATE.format(
            citacao=" ".join(citacao.split()), opcoes=montar_opcoes(cabecalhos)
        )
        for citacao, cabecalhos in disputas
    ]
    respostas = qwen.gerar_lote(PROMPT_SISTEMA, prompts, max_novos_tokens=8)
    return [
        _indice_da_resposta(resposta.texto, len(cabecalhos))
        for resposta, (_, cabecalhos) in zip(respostas, disputas, strict=True)
    ]
