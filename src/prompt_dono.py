# -*- coding: utf-8 -*-
"""
Prompt de classificação "dono vs citação" via LLM (Qwen3-8B).

Diferente da extração de span (prompt_extracao.py), esta tarefa não tem
risco de alucinação: o modelo não gera nem localiza nada, só classifica
um trecho de texto que já existe e cuja posição já conhecemos. A pergunta
é fechada e a resposta é restrita a duas palavras — não há espaço para o
modelo "inventar" texto que precisaria de verificação posterior.
"""

PROMPT_SISTEMA = """Você analisa um trecho de um documento jurídico (acórdão) \
e decide se o número de processo destacado nele é o número DO PRÓPRIO \
documento, ou se é uma citação a OUTRO processo mencionado como referência \
ou precedente dentro do texto.

Sinais de que é o PRÓPRIO processo (DONO):
- O número aparece junto de uma identificação formal do processo, como \
"RELATOR :", "RECORRENTE :", "AGRAVANTE :", "EMBARGANTE :" (com dois-pontos, \
tipicamente em maiúsculas) — os campos de qualificação das partes do caso.
- Ou aparece em frases como "em que é Recorrente/Embargante/Agravante ...".

Sinais de que é uma CITAÇÃO a outro processo:
- O número aparece dentro de uma frase de fundamentação ou ementa, \
frequentemente entre parênteses, citando jurisprudência: "(REsp 123.456/SP, \
relator Ministro Fulano, Segunda Turma, julgado em .../.../...)".
- O nome do relator aparece em minúsculas, seguido de "Turma", "julgado em" \
ou "DJe" — formato de referência bibliográfica de precedente, não de \
identificação do próprio caso.

Responda apenas com uma das duas palavras, sem explicação: DONO ou CITACAO.
Se o trecho não tiver nenhum dos sinais acima, responda CITACAO (na dúvida, \
não assuma que é o próprio processo)."""

PROMPT_USUARIO_TEMPLATE = """Trecho do documento (o número em análise aparece \
destacado entre [[ ]]):

{contexto_com_marcacao}

O número destacado é o DONO deste documento ou uma CITACAO a outro processo?"""


def montar_contexto_com_marcacao(texto: str, inicio: int, fim: int, janela: int = 150) -> str:
    """Extrai uma janela de texto ao redor do identificador (posições
    já conhecidas — vêm de buscar_candidatos) e marca visualmente o
    identificador com [[ ]], para o modelo saber exatamente qual número
    está em análise (pode haver outros números na mesma janela)."""
    ini_janela = max(0, inicio - janela)
    fim_janela = min(len(texto), fim + janela)
    return (
        texto[ini_janela:inicio]
        + "[[" + texto[inicio:fim] + "]]"
        + texto[fim:fim_janela]
    )


def classificar_dono_ou_citacao_lote(
    qwen: "QwenClassificador", contextos: list[tuple[str, int, int]]
) -> list[bool]:
    """Versão em lote: uma passada pela GPU para vários candidatos.

    `contextos` é uma lista de (texto, inicio, fim). A resposta útil tem 1
    token, então em série o custo é quase todo overhead — em lote, dezenas
    de classificações custam praticamente o mesmo que uma."""
    if not contextos:
        return []
    prompts = [
        PROMPT_USUARIO_TEMPLATE.format(
            contexto_com_marcacao=montar_contexto_com_marcacao(texto, inicio, fim)
        )
        for texto, inicio, fim in contextos
    ]
    respostas = qwen.gerar_lote(PROMPT_SISTEMA, prompts, max_novos_tokens=8)
    return [r.texto.strip().upper().startswith("DONO") for r in respostas]


def classificar_dono_ou_citacao(qwen: "QwenClassificador", texto: str, inicio: int, fim: int) -> bool:
    """True = documento é o dono do processo; False = citação a terceiro.
    Qualquer resposta que não seja exatamente "DONO" é tratada como
    CITACAO — mesmo viés conservador do prompt (na dúvida, não assume
    dono), aplicado também a respostas mal-formadas do modelo."""
    contexto = montar_contexto_com_marcacao(texto, inicio, fim)
    # resposta esperada é 1 palavra ("DONO" ou "CITACAO") — max_novos_tokens
    # pequeno evita gerar até 512 tokens à toa, acelera bastante em lote
    resposta = qwen.gerar(
        PROMPT_SISTEMA,
        PROMPT_USUARIO_TEMPLATE.format(contexto_com_marcacao=contexto),
        max_novos_tokens=8,
    )
    return resposta.texto.strip().upper().startswith("DONO")
