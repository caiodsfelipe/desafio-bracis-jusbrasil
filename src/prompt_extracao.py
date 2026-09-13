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
2. Não invente citações. Se não tiver certeza de que um trecho é uma \
citação, não o inclua.
3. Inclua também citações sem número de processo, quando o texto se refere \
a um julgado por descrição — por exemplo "julgado do STF proferido em 2024 \
pela relatoria de Dias Toffoli". Nesses casos preencha tribunal, ano e \
relator com o que o texto informar.
4. Não inclua números que não são citação: protocolo, inscrição na OAB, \
número de folhas (fls.), valor da causa.
5. O número do processo da própria peça (o que aparece no cabeçalho, \
identificando os autos deste documento) NÃO é citação: inclua-o na lista \
com "e_numero_do_proprio_documento": true, para que seja descartado.
6. Responda apenas com uma lista JSON, sem texto antes ou depois, onde cada \
item tem os campos:
   - "trecho": o texto copiado literalmente (obrigatório)
   - "tribunal": sigla do tribunal, ou null
   - "ano": ano do julgado como número, ou null
   - "relator": nome do relator, ou null
   - "e_numero_do_proprio_documento": true ou false
7. Se não houver nenhuma citação no texto, responda: []

Exemplo de resposta:
[{"trecho": "REsp nº 1.741.784/PR", "tribunal": "STJ", "ano": null, "relator": null, "e_numero_do_proprio_documento": false},
 {"trecho": "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli", "tribunal": "STF", "ano": 2024, "relator": "Dias Toffoli", "e_numero_do_proprio_documento": false}]
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
        max_novos_tokens=2048,  # documento inteiro pode ter dezenas de citações
    )
    return parsear_resposta(resposta.texto)
