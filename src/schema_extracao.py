# -*- coding: utf-8 -*-
"""
Schema da saída do extrator via LLM.

Por que Pydantic e não Instructor/Outlines: rodamos o modelo via
transformers puro (ver llm_qwen.py — vLLM foi descartado por risco de
instalação no Kaggle), então não há `guided_json` nem constrained decoding
disponível. As bibliotecas de saída estruturada acrescentariam dependência
ao bundle reproduzível exigido pelas regras sem garantir mais do que
conseguimos aqui: o prompt define o contrato, e este schema VALIDA a
resposta, descartando o que não conformar em vez de confiar no modelo.

Campos escolhidos a partir do que o pipeline precisa decidir depois:
- `trecho`: única coisa que o modelo copia; a posição (inicio/fim) é
  recuperada em Python por busca no texto original (verificacao_substring),
  nunca informada pelo modelo — LLM não conta caracteres de forma confiável.
- `tribunal`/`ano`/`relator`: metadados da citação em prosa sem número
  ("julgado do STF de 2024, relator Dias Toffoli"). É o que permite a
  consulta por metadados que caracteriza a `incompleta` buscável (resolve
  para dezenas de candidatos -> sem critério de desempate).
- `e_numero_do_proprio_documento`: marca o distrator do cabeçalho (o número
  dos autos da própria peça, que a documentação do desafio diz não ser
  citação e contar como falso positivo se extraído).
"""
from pydantic import BaseModel, Field, ValidationError


class CitacaoExtraida(BaseModel):
    trecho: str = Field(
        description="Texto da citação copiado literalmente do documento, caractere por caractere."
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
        description="True se este número identifica o processo da própria peça (cabeçalho/autos), não uma citação.",
    )


def parsear_resposta(texto_resposta: str) -> list[CitacaoExtraida]:
    """Converte a resposta bruta do LLM na lista validada de citações.
    Descarta silenciosamente qualquer item que não conforme ao schema —
    resposta mal-formada é tratada como ausência de citação, nunca como
    dado a ser 'consertado' (mesmo viés conservador do resto do pipeline).
    Retorna [] se a resposta inteira for inválida."""
    import json

    texto = texto_resposta.strip()
    # o modelo às vezes embrulha o JSON em cerca de código markdown
    if texto.startswith("```"):
        texto = texto.split("```")[1] if "```" in texto[3:] else texto[3:]
        texto = texto.removeprefix("json").strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return []
    if not isinstance(dados, list):
        return []

    citacoes = []
    for item in dados:
        try:
            citacoes.append(CitacaoExtraida.model_validate(item))
        except ValidationError:
            continue
    return citacoes
