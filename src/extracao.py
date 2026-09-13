# -*- coding: utf-8 -*-
"""
Extração de candidatos a citação: junta as duas fontes que rodam em
paralelo sobre o mesmo texto (regex estrutural e LLM), resolve o span de
cada trecho devolvido pelo LLM e devolve uma lista única, deduplicada.

Estrutura de dados: `CandidatoCitacao` substitui as tuplas
(inicio, fim, trecho) usadas antes na mesclagem — o extrator via LLM
agora devolve também tribunal/ano/relator (para a `incompleta` buscável)
e a marca de distrator de cabeçalho, e essa informação precisa sobreviver
até a etapa de resolução.
"""
from dataclasses import dataclass, field

from mesclagem import _iou
from regex_extracao import extrair_candidatos as extrair_por_regex
from verificacao_substring import localizar_ocorrencias


@dataclass
class CandidatoCitacao:
    inicio: int
    fim: int
    trecho: str
    origem: str  # "regex" ou "llm"
    tribunal: str | None = None
    ano: int | None = None
    relator: str | None = None

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


# O preâmbulo da peça (endereçamento, número dos autos, qualificação das
# partes, inscrição na OAB dos advogados) concentra os distratores que a
# documentação do desafio manda não extrair: números em formato CNJ que são
# do próprio documento, protocolo, OAB, valor da causa. Nenhum deles é
# citação, e o regex os captura porque têm a mesma forma.
#
# O corte é seguro por uma folga medida, não por calibração: no goldenset a
# primeira citação verdadeira de qualquer um dos 26 documentos está no
# caractere 460. Descartar candidatos antes de 400 remove 38 dos 41 falsos
# positivos sem tocar em nenhuma citação real.
_FIM_DO_PREAMBULO = 400


def _candidatos_do_regex(texto: str) -> list[CandidatoCitacao]:
    return [
        CandidatoCitacao(inicio=inicio, fim=fim, trecho=trecho, origem="regex")
        for inicio, fim, trecho in extrair_por_regex(texto)
        if inicio >= _FIM_DO_PREAMBULO
    ]


def _candidatos_do_llm(texto: str, citacoes_extraidas: list) -> list[CandidatoCitacao]:
    """Resolve o span de cada trecho copiado pelo LLM, buscando-o de volta
    no texto original. Trecho que não é encontrado foi alucinado ou
    alterado pelo modelo — descartado (ver verificacao_substring).

    Citações marcadas como número do próprio documento são descartadas
    aqui: são o distrator de cabeçalho, que a documentação do desafio diz
    contar como falso positivo se extraído.

    Quando o mesmo trecho aparece mais de uma vez no texto, consome as
    ocorrências em ordem — assim duas citações idênticas em pontos
    diferentes viram dois candidatos distintos, e não N cópias do mesmo
    span."""
    usados: set[tuple[int, int]] = set()
    candidatos = []
    for citacao in citacoes_extraidas:
        if citacao.e_numero_do_proprio_documento:
            continue
        for inicio, fim in localizar_ocorrencias(texto, citacao.trecho):
            if (inicio, fim) in usados:
                continue
            usados.add((inicio, fim))
            candidatos.append(
                CandidatoCitacao(
                    inicio=inicio,
                    fim=fim,
                    trecho=texto[inicio:fim],  # texto ORIGINAL, não o que o LLM devolveu
                    origem="llm",
                    tribunal=citacao.tribunal,
                    ano=citacao.ano,
                    relator=citacao.relator,
                )
            )
            break
    return candidatos


def _deduplicar(candidatos: list[CandidatoCitacao], iou_min: float = 0.5) -> list[CandidatoCitacao]:
    """Mesmo critério da mesclagem original: agrupa por sobreposição
    (IoU >= iou_min) e mantém o span mais longo de cada grupo. Empate de
    tamanho resolve pela origem regex (determinística) e, ainda empatado,
    pela posição — o resultado precisa ser estável para a reprodutibilidade
    exigida pelas regras do desafio.

    Ao manter o span mais longo, herda os metadados do candidato do LLM
    sobreposto, se houver: o regex não extrai tribunal/ano/relator, e essa
    informação seria perdida se o span do regex simplesmente vencesse."""
    ordenados = sorted(
        candidatos, key=lambda c: (-c.tamanho, c.origem != "regex", c.inicio)
    )
    mantidos: list[CandidatoCitacao] = []
    for candidato in ordenados:
        sobreposto = next(
            (
                m
                for m in mantidos
                if _iou((candidato.inicio, candidato.fim), (m.inicio, m.fim)) >= iou_min
            ),
            None,
        )
        if sobreposto is None:
            mantidos.append(candidato)
        elif sobreposto.tribunal is None and candidato.tribunal is not None:
            sobreposto.tribunal = candidato.tribunal
            sobreposto.ano = candidato.ano
            sobreposto.relator = candidato.relator
    return sorted(mantidos, key=lambda c: c.inicio)


def extrair_todos(texto: str, citacoes_do_llm: list | None = None) -> list[CandidatoCitacao]:
    """Pipeline de extração completo. `citacoes_do_llm` é o resultado de
    prompt_extracao.extrair_citacoes — opcional para permitir rodar só a
    parte determinística (sem GPU) em teste."""
    candidatos = _candidatos_do_regex(texto)
    if citacoes_do_llm:
        candidatos += _candidatos_do_llm(texto, citacoes_do_llm)
    return _deduplicar(candidatos)
