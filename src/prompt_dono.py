# -*- coding: utf-8 -*-
"""
Prompt que decide se o número destacado num trecho identifica o processo
do próprio documento ou uma decisão citada dentro dele.

A pergunta é fechada e a resposta se limita a duas palavras. O modelo não
produz nem localiza texto: julga um trecho já delimitado.
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
- O número aparece numa LISTA de processos correlatos, itemizada com \
travessões ou marcadores e ligada por expressões como "envolvendo os IPMs \
nº ...", "(declinado)", "(prevento)", "em apenso", "conexo a". Uma lista de \
vários números seguidos é enumeração de outros feitos, não a identificação \
deste documento — mesmo que traga o nome do recurso por extenso antes do \
número.

ATENÇÃO: o nome do recurso escrito antes do número ("Recurso em Sentido \
Estrito nº ...", "Apelação nº ...") NÃO é sinal de DONO por si só — aparece \
igualmente em citações. O que caracteriza o DONO é o número vir acompanhado \
da identificação formal do julgamento: RELATOR/RELATORA, as partes \
qualificadas, o órgão julgador e a data da sessão.

Responda apenas com uma das duas palavras, sem explicação: DONO ou CITACAO.
Se o trecho não tiver nenhum dos sinais acima, responda CITACAO (na dúvida, \
não assuma que é o próprio processo)."""

PROMPT_USUARIO_TEMPLATE = """Trecho do documento (o número em análise aparece \
destacado entre [[ ]]):

{contexto_com_marcacao}

O número destacado é o DONO deste documento ou uma CITACAO a outro processo?"""


def montar_contexto_com_marcacao(texto: str, inicio: int, fim: int, janela: int = 150) -> str:
    """Janela de texto ao redor do identificador, com ele destacado entre
    [[ ]], já que a janela pode conter outros números."""
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
    """Classifica vários contextos (texto, inicio, fim) numa única
    passada pela GPU."""
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
    """Verdadeiro quando o documento é o processo citado. Qualquer
    resposta diferente de "DONO" é lida como citação a terceiro."""
    contexto = montar_contexto_com_marcacao(texto, inicio, fim)
    resposta = qwen.gerar(
        PROMPT_SISTEMA,
        PROMPT_USUARIO_TEMPLATE.format(contexto_com_marcacao=contexto),
        max_novos_tokens=8,
    )
    return resposta.texto.strip().upper().startswith("DONO")
