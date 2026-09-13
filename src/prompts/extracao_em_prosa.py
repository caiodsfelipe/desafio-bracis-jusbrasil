"""
Prompts que extraem as citações em prosa que os padrões estruturais não
alcançaram.
"""
from . import Prompt, registrar

V1 = Prompt(
    nome="extracao_em_prosa",
    versao="v1",
    nota=(
        "Pede todas as citações do documento, com identificador ou sem. "
        "Aposentada porque as citações com número já vinham dos padrões "
        "estruturais, e pedi-las de novo gerava spans concorrentes."
    ),
    texto="""Você localiza citações de jurisprudência e de lei dentro de \
textos jurídicos em português.

Copie cada citação exatamente como aparece no texto, caractere por \
caractere, incluindo quebras de linha, abreviações e erros de digitação. \
Não corrija, não complete, não normalize nada.

Responda apenas com uma lista JSON.""",
)

V2 = Prompt(
    nome="extracao_em_prosa",
    versao="v2",
    nota=(
        "Restringe o pedido às citações sem número e delimita a borda do "
        "trecho com exemplos do que não incluir. Os padrões estruturais "
        "cobrem as citações com identificador."
    ),
    texto="""Você localiza citações de jurisprudência (acórdãos, súmulas, \
decisões de tribunais) e de lei (artigos, códigos) dentro de textos \
jurídicos em português.

Regras obrigatórias:
1. Copie cada citação EXATAMENTE como aparece no texto, caractere por \
caractere, incluindo quebras de linha, abreviações e eventuais erros de \
digitação. Não corrija, não complete, não normalize nada.
2. Copie APENAS a citação em si, não a frase inteira em que ela aparece. \
Comece na designação do julgado (a sigla, o nome do recurso, ou "julgado do", \
"precedente do", "acórdão do") e termine no último elemento que identifica o \
julgado (o número com a UF, ou o nome do relator). Não inclua o que vem \
antes nem o que vem depois.
   Errado: "Invoca-se, ainda, a Reclamação nº 66.516/RO, no ponto em que afasta a exigência."
   Certo:  "Reclamação nº 66.516/RO"
3. Não invente citações. Se não tiver certeza de que um trecho é uma \
citação, não o inclua.
4. Liste SOMENTE as citações que NÃO trazem número identificador, aquelas \
em que o julgado ou a norma é referido por descrição. Dois casos:
   - julgado descrito por tribunal, ano e relator: "julgado do STF proferido \
em 2024 pela relatoria de Dias Toffoli";
   - norma referida sem o número do artigo: "artigo correspondente do Código \
de Processo Civil".
   Citações que trazem número de processo, de súmula ou de artigo já são \
tratadas por outro componente: NÃO as inclua.
5. Responda apenas com uma lista JSON, sem texto antes ou depois, onde cada \
item tem os campos:
   - "trecho": o texto copiado literalmente (obrigatório)
   - "tribunal": sigla do tribunal, ou null
   - "ano": ano do julgado como número, ou null
   - "relator": nome do relator, ou null
6. Se não houver nenhuma citação desse tipo no texto, responda: []

Exemplo de resposta:
[{"trecho": "julgado do STF proferido em 2024 pela relatoria de Dias Toffoli", "tribunal": "STF", "ano": 2024, "relator": "Dias Toffoli"}]
""",
)

V3 = Prompt(
    nome="extracao_em_prosa",
    versao="v3",
    nota=(
        "Anuncia que os padrões estruturais já cobrem os moldes correntes de "
        "citação em prosa e pede as formas que fogem deles, para que o "
        "modelo complemente a extração determinística em vez de repeti-la."
    ),
    texto="""Você localiza, em textos jurídicos em português, as citações a \
julgados que NÃO trazem número de processo.

Regras obrigatórias:
1. Copie cada citação EXATAMENTE como aparece no texto, caractere por \
caractere, incluindo quebras de linha, abreviações e eventuais erros de \
digitação. Não corrija, não complete, não normalize nada.
2. Copie APENAS a citação em si, não a frase inteira em que ela aparece. \
Comece na designação do julgado e termine no último elemento que o \
identifica (o nome do relator, ou o ano).
   Errado: "Como já se reconheceu no julgado do STM proferido em 2023 pela relatoria de CARLOS OLIVEIRA, a distinção não se sustenta."
   Certo:  "julgado do STM proferido em 2023 pela relatoria de CARLOS OLIVEIRA"
3. NÃO inclua citações que tragam número de processo, de súmula, de tema ou \
de artigo de lei: elas já foram extraídas por outro componente.
4. As formas mais correntes já foram extraídas também, e repeti-las não \
acrescenta nada:
   - "julgado/precedente/acórdão do TRIBUNAL, de ANO, relatoria de NOME"
   - "ESPÉCIE DE RECURSO do TRIBUNAL, de ANO, Rel. Min. NOME"
   - "artigo correspondente do CÓDIGO"
   Procure o que foge desses moldes: o julgado referido pelo órgão \
fracionário, pelo voto condutor, pela ementa, ou por qualquer descrição que \
aponte um precedente sem nomear seu número.
5. Não invente citações. Na dúvida, não inclua.
6. Responda apenas com uma lista JSON, sem texto antes ou depois, onde cada \
item tem os campos:
   - "trecho": o texto copiado literalmente (obrigatório)
   - "tribunal": sigla do tribunal, ou null
   - "ano": ano do julgado como número, ou null
   - "relator": nome do relator, ou null
7. Se não houver nenhuma citação desse tipo, responda: []

Exemplo de resposta:
[{"trecho": "voto condutor do Ministro Barroso no julgamento de 2024", "tribunal": "STF", "ano": 2024, "relator": "Barroso"}]
""",
)

VIGENTE = registrar((V1, V2, V3))
