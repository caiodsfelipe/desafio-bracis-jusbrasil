# -*- coding: utf-8 -*-
"""
Prompt de extração de citações via LLM (Qwen3-8B).

Regra de segurança: o modelo NUNCA informa inicio/fim (LLMs não contam
caracteres de forma confiável). Ele só copia o trecho literal; o código
Python depois busca essa string de volta no texto original para achar a
posição exata (verificacao_substring.py). Se a busca falhar, o candidato
é descartado.

A saída é validada contra schema_extracao.CitacaoExtraida — o prompt
define o contrato, o schema rejeita o que não conformar.
"""

PROMPT_SISTEMA = """Você localiza citações de jurisprudência (acórdãos, súmulas, \
decisões de tribunais) e de lei (artigos, códigos) dentro de textos jurídicos \
em português.

Regras obrigatórias:
1. Copie cada citação EXATAMENTE como aparece no texto, caractere por \
caractere — incluindo quebras de linha, abreviações e eventuais erros de \
digitação. Não corrija, não complete, não normalize nada.
1b. Copie APENAS a citação em si, não a frase inteira em que ela aparece. \
Comece na designação do julgado (a sigla, o nome do recurso, ou "julgado do", \
"precedente do", "acórdão do") e termine no último elemento que identifica o \
julgado (o número com a UF, ou o nome do relator). Não inclua o que vem \
antes ("Invoca-se, ainda,", "Como já se reconheceu no") nem o que vem depois \
(", no ponto em que afasta a exigência combatida").
   Errado: "Invoca-se, ainda, a Reclamação nº 66.516/RO, no ponto em que afasta a exigência combatida."
   Certo:  "Reclamação nº 66.516/RO"
   Errado: "Como já se reconheceu no julgado do STM proferido em 2023 pela relatoria de CARLOS AUGUSTO AMARAL OLIVEIRA, a distinção pretendida não se sustenta."
   Certo:  "julgado do STM proferido em 2023 pela relatoria de CARLOS AUGUSTO AMARAL OLIVEIRA"
2. Não invente citações. Se não tiver certeza de que um trecho é uma \
citação, não o inclua.
3. Liste SOMENTE as citações SEM número de processo — aquelas em que o \
julgado é descrito por tribunal, ano e relator, como "julgado do STF \
proferido em 2024 pela relatoria de Dias Toffoli" ou "precedente do STM de \
2023, da relatoria de Marco Antonio". Citações que trazem número de \
processo, súmula ou artigo de lei já são tratadas por outro componente: \
NÃO as inclua.
4. Responda apenas com uma lista JSON, sem texto antes ou depois, onde cada \
item tem os campos:
   - "trecho": o texto copiado literalmente (obrigatório)
   - "tribunal": sigla do tribunal, ou null
   - "ano": ano do julgado como número, ou null
   - "relator": nome do relator, ou null
5. Se não houver nenhuma citação desse tipo no texto, responda: []

Exemplo de resposta:
[{"trecho": "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli", "tribunal": "STF", "ano": 2024, "relator": "Dias Toffoli"},
 {"trecho": "precedente do STM de 2023, da relatoria de Marco Antonio", "tribunal": "STM", "ano": 2023, "relator": "Marco Antonio"}]
"""

PROMPT_USUARIO_TEMPLATE = """Texto do documento:

{texto}

Liste as citações encontradas, seguindo as regras."""


def extrair_citacoes(qwen, texto: str) -> list:
    """Roda o LLM sobre o texto e devolve a lista validada de
    CitacaoExtraida (ver schema_extracao). O span ainda não está resolvido
    aqui — quem chama usa verificacao_substring.localizar_ocorrencias para
    achar inicio/fim de cada trecho no texto original."""
    from schema_extracao import parsear_resposta

    resposta = qwen.gerar(
        PROMPT_SISTEMA,
        PROMPT_USUARIO_TEMPLATE.format(texto=texto),
        # só citações em prosa (as com número vêm do regex) — são poucas e
        # curtas por documento, e o parser recupera itens completos se
        # mesmo assim a resposta truncar
        max_novos_tokens=768,
    )
    return parsear_resposta(resposta.texto)
