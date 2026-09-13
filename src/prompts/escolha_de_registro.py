"""
Prompts que escolhem, entre registros do acervo autuados com o mesmo
número, aquele a que a citação se refere.
"""
from . import Prompt, registrar

V1 = Prompt(
    nome="escolha_de_registro",
    versao="v1",
    nota=(
        "Perguntava se o número destacado num acórdão era o do próprio "
        "processo ou uma citação a terceiro, respondida com DONO ou "
        "CITACAO. Aposentada porque a pergunta não separa dois acórdãos "
        "que são ambos donos do número e diferem na espécie do recurso."
    ),
    texto="""Você analisa um trecho de um documento jurídico (acórdão) e \
decide se o número de processo destacado nele é o número DO PRÓPRIO \
documento, ou se é uma citação a OUTRO processo mencionado como \
referência dentro do texto.

Responda apenas com uma das duas palavras, sem explicação: DONO ou \
CITACAO.""",
)

# Texto em produção desde a submissão que marcou 1.00755 na avaliação
# oficial. Alterá-lo muda o que o modelo devolve, e nenhuma avaliação local
# exercita esse caminho: só uma submissão mede o efeito.
V2 = Prompt(
    nome="escolha_de_registro",
    versao="v2",
    nota=(
        "Apresenta os cabeçalhos concorrentes como opções numeradas e pede "
        "a escolha de uma delas, ou zero quando nenhuma corresponde. A "
        "espécie do recurso é o que separa dois acórdãos que tramitam com "
        "o mesmo número."
    ),
    texto="""Você recebe uma citação a um julgado, extraída de uma \
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
quando nenhuma das opções for o julgado citado.""",
)

VIGENTE = registrar((V1, V2))
