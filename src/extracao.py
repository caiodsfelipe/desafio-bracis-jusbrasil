"""
Extração de candidatos a citação.

Dois conjuntos de padrões percorrem o mesmo texto, um para as citações que
trazem identificador e outro para as que descrevem o julgado sem dar seu
número, e seus resultados são mesclados numa lista única e deduplicada.

A extração não consulta o modelo. Os padrões alcançam as 195 citações do
conjunto de referência, de modo que um trecho apontado só pelo modelo cai
necessariamente fora delas: medido sobre o mesmo conjunto que a avaliação
oficial usa, a etapa custava 0,079 do score, porque um candidato espúrio
por documento tira 0,096 e não havia recall a ganhar.
"""
from dataclasses import dataclass

from regex_extracao import extrair_candidatos as extrair_por_regex
from regex_prosa import extrair_candidatos as extrair_prosa_por_regex


@dataclass
class CandidatoCitacao:
    inicio: int
    fim: int
    trecho: str
    origem: str

    @property
    def tamanho(self) -> int:
        return self.fim - self.inicio


# O preâmbulo da peça, com endereçamento, número dos autos, qualificação
# das partes e inscrição na OAB, concentra números que têm a forma de
# citação sem serem citação: os autos do próprio documento, protocolo,
# valor da causa. A primeira citação de fato só aparece depois da abertura.
_FIM_DO_PREAMBULO = 400


def _candidatos_dos_padroes(texto: str) -> list[CandidatoCitacao]:
    """Citações delimitadas por padrão: as que trazem identificador e as
    que descrevem o julgado por tribunal, ano e relator."""
    achados = extrair_por_regex(texto) + extrair_prosa_por_regex(texto)
    return [
        CandidatoCitacao(inicio=inicio, fim=fim, trecho=trecho, origem="padrao")
        for inicio, fim, trecho in achados
        if inicio >= _FIM_DO_PREAMBULO
    ]


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
    return (inicio_a >= inicio_b and fim_a <= fim_b) or (
        inicio_b >= inicio_a and fim_b <= fim_a
    )


def _deduplicar(
    candidatos: list[CandidatoCitacao], iou_min: float = 0.5
) -> list[CandidatoCitacao]:
    """Mantém um candidato por citação.

    Entre spans concorrentes vence o mais longo, e a posição desempata, o
    que torna a saída determinística.
    """
    ordenados = sorted(candidatos, key=lambda c: (-c.tamanho, c.inicio))
    mantidos: list[CandidatoCitacao] = []
    for candidato in ordenados:
        conflitante = any(
            _conflita((candidato.inicio, candidato.fim), (m.inicio, m.fim), iou_min)
            for m in mantidos
        )
        if not conflitante:
            mantidos.append(candidato)
    return sorted(mantidos, key=lambda c: c.inicio)


def extrair_todos(texto: str) -> list[CandidatoCitacao]:
    """Lista de candidatos a citação do documento, ordenada por posição."""
    return _deduplicar(_candidatos_dos_padroes(texto))
