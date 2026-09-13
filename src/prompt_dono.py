# -*- coding: utf-8 -*-
"""
Prompt que escolhe, entre os registros do acervo que trazem o mesmo número,
aquele a que a citação se refere.

A pergunta só é feita quando a posição do identificador não decide: vários
processos foram autuados com o mesmo número e diferem apenas na espécie de
recurso. A resposta é o índice de uma das opções apresentadas, e o modelo
não produz nem localiza texto — escolhe entre alternativas já delimitadas.
"""

PROMPT_SISTEMA = """Você recebe uma citação a um julgado, extraída de uma \
peça jurídica, e uma lista numerada de acórdãos cujo número de processo \
coincide com o citado.

Um mesmo número identifica processos diferentes quando a espécie de recurso \
difere: o recurso especial, o agravo interno nele interposto e os embargos \
de divergência que o seguem tramitam com o mesmo número e são julgados em \
acórdãos distintos. O que separa um do outro é a espécie do recurso, \
indicada pela sigla ou pelo nome por extenso no início de cada acórdão.

Compare a espécie de recurso da citação com a de cada opção:
- "AgInt no Recurso Especial" corresponde a "AgInt no RECURSO ESPECIAL", \
não a "EMBARGOS DE DIVERGÊNCIA EM RESP";
- "AgARR" é agravo em recurso de revista com agravo, e corresponde a \
"RECURSO DE REVISTA COM AGRAVO", não a "AGRAVO DE INSTRUMENTO EM RECURSO \
DE REVISTA" (AIRR);
- "EDcl" designa embargos de declaração, "AgRg" e "AgInt" o agravo interno, \
"RHC" o recurso em habeas corpus.

Nem sempre uma das opções é o julgado citado. O número pode aparecer nos \
acórdãos apenas dentro de fundamentações, referindo-se a um processo que \
não está no acervo: nesse caso, nenhuma opção é a citação, ainda que todas \
contenham o número.

Responda apenas com o número da opção escolhida, sem explicação, ou com 0 \
quando nenhuma das opções for o julgado citado."""

PROMPT_USUARIO_TEMPLATE = """Citação encontrada na peça:

{citacao}

Opções do acervo:

{opcoes}

Qual opção corresponde à citação?"""

_CARACTERES_DE_CABECALHO = 200


def montar_opcoes(cabecalhos: list[str]) -> str:
    """Lista numerada a partir de 1, com o início de cada acórdão — é onde
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


def escolher_registro_lote(
    qwen: "QwenClassificador", disputas: list[tuple[str, list[str]]]
) -> list[int]:
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
        for resposta, (_, cabecalhos) in zip(respostas, disputas)
    ]
