"""
Extração de candidatos a citação.

Fontes independentes percorrem o mesmo texto, os padrões estruturais e o
LLM, e seus resultados são mesclados numa lista única e deduplicada. O
span de cada trecho devolvido pelo LLM é resolvido contra o texto original
antes de entrar na lista.
"""
from dataclasses import dataclass

from regex_extracao import extrair_candidatos as extrair_por_regex
from regex_prosa import extrair_candidatos as extrair_prosa_por_regex
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


# O preâmbulo da peça, com endereçamento, número dos autos, qualificação
# das partes e inscrição na OAB, concentra números que têm a forma de citação
# sem serem citação: os autos do próprio documento, protocolo, valor da
# causa. A primeira citação de fato só aparece depois da abertura do texto.
_FIM_DO_PREAMBULO = 400


def _candidatos_do_regex(texto: str) -> list[CandidatoCitacao]:
    """Citações delimitadas por padrão: as que trazem identificador e as
    que descrevem o julgado por tribunal, ano e relator."""
    achados = extrair_por_regex(texto) + extrair_prosa_por_regex(texto)
    return [
        CandidatoCitacao(inicio=inicio, fim=fim, trecho=trecho, origem="regex")
        for inicio, fim, trecho in achados
        if inicio >= _FIM_DO_PREAMBULO
    ]


def _candidatos_do_llm(texto: str, citacoes_extraidas: list) -> list[CandidatoCitacao]:
    """Resolve o span de cada trecho copiado pelo LLM, localizando-o no
    texto original; trecho que não é encontrado ali é descartado.

    Quando o mesmo trecho ocorre mais de uma vez, as ocorrências são
    consumidas em ordem, de modo que duas citações idênticas em pontos
    diferentes do documento se tornem candidatos distintos."""
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
                    trecho=texto[inicio:fim],
                    origem="llm",
                    tribunal=citacao.tribunal,
                    ano=citacao.ano,
                    relator=citacao.relator,
                )
            )
            break
    return candidatos


def _iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    """Interseção sobre união entre dois spans. O limiar de 0,5 usado
    adiante é o mesmo da avaliação oficial."""
    inicio_a, fim_a = a
    inicio_b, fim_b = b
    intersecao = max(0, min(fim_a, fim_b) - max(inicio_a, inicio_b))
    if intersecao == 0:
        return 0.0
    uniao = (fim_a - inicio_a) + (fim_b - inicio_b) - intersecao
    return intersecao / uniao


def _conflita(a: tuple[int, int], b: tuple[int, int], iou_min: float) -> bool:
    """Dois spans representam a mesma citação.

    A sobreposição por IoU cobre bordas parecidas; a contenção cobre o caso
    de um span envolver o outro por inteiro, o que produz IoU baixo mas
    ainda é uma única citação.
    """
    if _iou(a, b) >= iou_min:
        return True
    inicio_a, fim_a = a
    inicio_b, fim_b = b
    return (inicio_a >= inicio_b and fim_a <= fim_b) or (inicio_b >= inicio_a and fim_b <= fim_a)


def _deduplicar(candidatos: list[CandidatoCitacao], iou_min: float = 0.5) -> list[CandidatoCitacao]:
    """Mantém um candidato por citação.

    O candidato do regex prevalece, por delimitar a citação com precisão;
    entre spans da mesma origem vence o mais longo, e a posição desempata,
    o que torna a saída determinística. Os metadados extraídos pelo LLM
    (tribunal, ano, relator) são preservados no candidato vencedor.
    """
    ordenados = sorted(
        candidatos, key=lambda c: (c.origem != "regex", -c.tamanho, c.inicio)
    )
    mantidos: list[CandidatoCitacao] = []
    for candidato in ordenados:
        conflitante = next(
            (
                m
                for m in mantidos
                if _conflita((candidato.inicio, candidato.fim), (m.inicio, m.fim), iou_min)
            ),
            None,
        )
        if conflitante is None:
            mantidos.append(candidato)
        elif conflitante.tribunal is None and candidato.tribunal is not None:
            conflitante.tribunal = candidato.tribunal
            conflitante.ano = candidato.ano
            conflitante.relator = candidato.relator
    return sorted(mantidos, key=lambda c: c.inicio)


def extrair_todos(texto: str, citacoes_do_llm: list | None = None) -> list[CandidatoCitacao]:
    """Lista de candidatos a citação do documento, ordenada por posição.

    `citacoes_do_llm` é a saída de `prompt_extracao.extrair_citacoes`;
    omiti-la executa apenas a extração determinística.
    """
    candidatos = _candidatos_do_regex(texto)
    if citacoes_do_llm:
        candidatos += _candidatos_do_llm(texto, citacoes_do_llm)
    return _deduplicar(candidatos)
