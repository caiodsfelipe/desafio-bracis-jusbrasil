"""
Prompt de extração de citações via LLM (Qwen3-8B).

Regra de segurança: o modelo NUNCA informa inicio/fim (LLMs não contam
caracteres de forma confiável). Ele só copia o trecho literal; o código
Python depois busca essa string de volta no texto original para achar a
posição exata (verificacao_substring.py). Se a busca falhar, o candidato
é descartado.

A saída é validada contra schema_extracao.CitacaoExtraida: o prompt
define o contrato, o schema rejeita o que não conformar.
"""
from prompts.extracao_em_prosa import VIGENTE

PROMPT_SISTEMA = VIGENTE.texto

PROMPT_USUARIO_TEMPLATE = """Texto do documento:

{texto}

Liste as citações encontradas, seguindo as regras."""


def extrair_citacoes(qwen, texto: str) -> list:
    """Roda o LLM sobre o texto e devolve a lista validada de
    CitacaoExtraida (ver schema_extracao). O span ainda não está resolvido
    aqui; quem chama usa verificacao_substring.localizar_ocorrencias para
    achar inicio/fim de cada trecho no texto original."""
    from schema_extracao import parsear_resposta

    resposta = qwen.gerar(
        PROMPT_SISTEMA,
        PROMPT_USUARIO_TEMPLATE.format(texto=texto),
        # só citações em prosa (as com número vêm do regex), que são poucas e
        # curtas por documento, e o parser recupera itens completos se
        # mesmo assim a resposta truncar
        max_novos_tokens=768,
    )
    return parsear_resposta(resposta.texto)
