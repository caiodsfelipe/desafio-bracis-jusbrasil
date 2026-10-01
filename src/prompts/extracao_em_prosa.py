"""
Prompts que extraíam as citações em prosa, hoje fora de uso.

A família está aposentada. Os padrões de regex_prosa.py alcançam as 195
citações do conjunto de referência sozinhos, e o conjunto que a avaliação
oficial usa é esse mesmo. Um trecho apontado só pelo modelo cai
necessariamente fora das formas já cobertas e entra como candidato sem
nada que o sustente; medido sobre o mesmo conjunto, a etapa custava 0,079
do score, porque um candidato espúrio por documento tira 0,096 e não havia
recall a ganhar.

O histórico fica registrado: se um dia a extração determinística deixar de
bastar, o texto de partida está aqui, com a medição que o aposentou.
"""
from . import Prompt

V1 = Prompt(
    nome="extracao_em_prosa",
    versao="v1",
    nota=(
        "Pedia todas as citações do documento, com identificador ou sem. "
        "Aposentada porque as citações com número já vinham dos padrões "
        "estruturais, e pedi-las de novo gerava spans concorrentes."
    ),
    texto="""Você localiza citações de jurisprudência e de lei dentro de \
textos jurídicos em português.

Copie cada citação exatamente como aparece no texto, caractere por \
caractere. Não corrija, não complete, não normalize nada.

Responda apenas com uma lista JSON.""",
)

V2 = Prompt(
    nome="extracao_em_prosa",
    versao="v2",
    nota=(
        "Restringia o pedido às citações sem número e delimitava a borda do "
        "trecho com exemplos do que não incluir. Aposentada junto com a "
        "etapa: os padrões cobrem essas citações e o que o modelo acrescenta "
        "a elas é candidato espúrio."
    ),
    texto="""Você localiza citações de jurisprudência (acórdãos, súmulas, \
decisões de tribunais) e de lei (artigos, códigos) dentro de textos jurídicos \
em português.

Regras obrigatórias:
1. Copie cada citação EXATAMENTE como aparece no texto, caractere por \
caractere, incluindo quebras de linha, abreviações e eventuais erros de \
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
3. Liste SOMENTE as citações que NÃO trazem número identificador, aquelas \
em que o julgado ou a norma é referido por descrição. Dois casos:
   - julgado descrito por tribunal, ano e relator: "julgado do STF proferido \
em 2024 pela relatoria de Dias Toffoli", "precedente do STM de 2023, da \
relatoria de Marco Antonio", "Rcl de 2021, Rel. Min. Rosa Weber";
   - norma referida sem o número do artigo: "artigo correspondente do Código \
de Processo Civil", "o dispositivo legal de regência".
   Citações que trazem número de processo, número de súmula ou número de \
artigo já são tratadas por outro componente: NÃO as inclua.
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
""",
)

APOSENTADOS = (V1, V2)
