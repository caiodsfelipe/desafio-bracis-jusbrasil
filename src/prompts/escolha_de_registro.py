"""
Prompts que escolhem, entre registros do acervo autuados com o mesmo
número, aquele a que a citação se refere.
"""
from . import Prompt, registrar

V1 = Prompt(
    nome="escolha_de_registro",
    versao="v1",
    nota=(
        "Pergunta se o número destacado num acórdão é o do próprio processo "
        "ou uma citação a terceiro, respondida com DONO ou CITACAO. "
        "Aposentada porque a pergunta não separa dois acórdãos que são ambos "
        "donos do número e diferem apenas na espécie do recurso."
    ),
    texto="""Você analisa um trecho de um documento jurídico (acórdão) \
e decide se o número de processo destacado nele é o número DO PRÓPRIO \
documento, ou se é uma citação a OUTRO processo mencionado como referência \
ou precedente dentro do texto.

Sinais de que é o PRÓPRIO processo (DONO):
- O número aparece junto de uma identificação formal do processo, como \
"RELATOR :", "RECORRENTE :", "AGRAVANTE :", "EMBARGANTE :" (com dois-pontos, \
tipicamente em maiúsculas), os campos de qualificação das partes do caso.
- Ou aparece em frases como "em que é Recorrente/Embargante/Agravante ...".

Sinais de que é uma CITAÇÃO a outro processo:
- O número aparece dentro de uma frase de fundamentação ou ementa, \
frequentemente entre parênteses, citando jurisprudência.
- O nome do relator aparece em minúsculas, seguido de "Turma", "julgado em" \
ou "DJe", formato de referência bibliográfica de precedente.
- O número aparece numa lista de processos correlatos.

Responda apenas com uma das duas palavras, sem explicação: DONO ou CITACAO.""",
)

V2 = Prompt(
    nome="escolha_de_registro",
    versao="v2",
    nota=(
        "Passa a apresentar os cabeçalhos concorrentes como opções numeradas "
        "e a pedir a escolha de uma delas. A espécie do recurso é o que "
        "separa dois acórdãos que tramitam com o mesmo número."
    ),
    texto="""Você recebe uma citação a um julgado, extraída de uma peça \
jurídica, e uma lista numerada de acórdãos cujo número de processo coincide \
com o citado.

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
"RHC" o recurso em habeas corpus, "RMS" o recurso em mandado de segurança.

Responda apenas com o número da opção escolhida, sem explicação.""",
)

VIGENTE = registrar((V1, V2))
