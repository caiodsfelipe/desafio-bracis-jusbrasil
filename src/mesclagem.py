# -*- coding: utf-8 -*-
"""
Mesclagem/deduplicação dos candidatos vindos de regex e LLM (rodam em
paralelo sobre o mesmo texto, sem um decidir o território do outro).

Critério de "mesma citação" (a deduplicar): IoU >= 0.5 entre os spans —
o mesmo limiar que a métrica oficial (kaggle_metric.py) usa para casar
predição com gabarito. Reaproveita um conceito já validado em vez de
inventar um critério novo.

Critério de desempate dentro de um grupo: mantém o span mais longo — mais
contexto capturado tende a ser mais completo (ex.: com a UF no final).
"""


def _iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    inicio_a, fim_a = a
    inicio_b, fim_b = b
    inter = max(0, min(fim_a, fim_b) - max(inicio_a, inicio_b))
    if inter == 0:
        return 0.0
    uniao = (fim_a - inicio_a) + (fim_b - inicio_b) - inter
    return inter / uniao


def mesclar_candidatos(
    candidatos_regex: list[tuple[int, int, str]],
    candidatos_llm: list[tuple[int, int, str]],
    iou_min: float = 0.5,
) -> list[tuple[int, int, str]]:
    """Junta as duas listas e remove duplicatas por sobreposição (IoU >=
    iou_min), mantendo o span mais longo de cada grupo sobreposto."""
    todos = list(candidatos_regex) + list(candidatos_llm)
    todos.sort(key=lambda c: c[1] - c[0], reverse=True)  # maior span primeiro

    mantidos: list[tuple[int, int, str]] = []
    for candidato in todos:
        inicio, fim, _ = candidato
        sobrepoe_algum_mantido = any(
            _iou((inicio, fim), (m_inicio, m_fim)) >= iou_min
            for m_inicio, m_fim, _ in mantidos
        )
        if not sobrepoe_algum_mantido:
            mantidos.append(candidato)

    return sorted(mantidos, key=lambda c: c[0])
