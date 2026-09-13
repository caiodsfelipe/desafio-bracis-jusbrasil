"""
Schema da saída do extrator via LLM.

O prompt define o formato esperado e este schema valida o que chega,
descartando itens que não o respeitem. O modelo devolve apenas o texto da
citação: a posição é recuperada depois, procurando o trecho no documento
original, porque um modelo de linguagem não conta caracteres com precisão.

Os metadados de tribunal, ano e relator acompanham as citações que
descrevem o julgado sem dar seu número.
"""
from pydantic import BaseModel, Field, ValidationError


class CitacaoExtraida(BaseModel):
    trecho: str = Field(
        description="Texto da citação copiado literalmente do documento."
    )
    tribunal: str | None = Field(
        default=None, description="Sigla do tribunal, se mencionada (STF, STJ, TST, TSE, STM)."
    )
    ano: int | None = Field(
        default=None, description="Ano do julgado, se mencionado."
    )
    relator: str | None = Field(
        default=None, description="Nome do relator, se mencionado."
    )
    e_numero_do_proprio_documento: bool = Field(
        default=False,
        description=(
            "Verdadeiro quando o número identifica o processo da própria "
            "peça, não uma citação."
        ),
    )


def parsear_resposta(texto_resposta: str) -> list[CitacaoExtraida]:
    """Citações válidas presentes na resposta. Itens fora do formato são
    descartados, e uma resposta inteiramente inválida resulta em lista
    vazia."""
    import json

    texto = texto_resposta.strip()
    # a resposta pode vir envolta em cerca de código
    if texto.startswith("```"):
        texto = texto.split("```")[1] if "```" in texto[3:] else texto[3:]
        texto = texto.removeprefix("json").strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        # A resposta pode terminar no meio de um item, quando o limite de
        # tokens é atingido; os itens completos ainda são aproveitáveis.
        dados = _objetos_completos(texto)
    if not isinstance(dados, list):
        return []

    citacoes = []
    for item in dados:
        try:
            citacoes.append(CitacaoExtraida.model_validate(item))
        except ValidationError:
            continue
    return citacoes


def _objetos_completos(texto: str) -> list[dict]:
    """Objetos JSON completos do primeiro nível, ignorando um item
    truncado ao fim. Aspas e escapes são rastreados para que chaves dentro
    de strings não sejam confundidas com delimitadores."""
    import contextlib
    import json

    objetos = []
    profundidade = 0
    inicio = None
    dentro_de_string = False
    escapado = False

    for posicao, caractere in enumerate(texto):
        if dentro_de_string:
            if escapado:
                escapado = False
            elif caractere == "\\":
                escapado = True
            elif caractere == '"':
                dentro_de_string = False
            continue
        if caractere == '"':
            dentro_de_string = True
        elif caractere == "{":
            if profundidade == 0:
                inicio = posicao
            profundidade += 1
        elif caractere == "}":
            profundidade -= 1
            if profundidade == 0 and inicio is not None:
                with contextlib.suppress(json.JSONDecodeError):
                    objetos.append(json.loads(texto[inicio : posicao + 1]))
                inicio = None
    return objetos
