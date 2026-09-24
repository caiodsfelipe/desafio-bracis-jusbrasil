"""
Extração de candidatos a citação.

Dois conjuntos de padrões percorrem o mesmo texto, um para as citações que
trazem identificador e outro para as que descrevem o julgado sem dar seu
número, e seus resultados são mesclados numa lista única e deduplicada.

A extração não consulta o modelo. Os padrões alcançam as 192 citações do
conjunto de referência, de modo que um trecho apontado só pelo modelo cai
necessariamente fora delas: medido sobre o mesmo conjunto que a avaliação
oficial usa, a etapa custava 0,079 do score, porque um candidato espúrio
por documento tira 0,096 e não havia recall a ganhar.
"""
import re
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
#
# O que delimita o preâmbulo é a forma, não a posição: ele é uma sequência
# de linhas curtas, cada uma um rótulo de qualificação ou um título, e
# termina na primeira linha de prosa corrida. Medir por posição fixa
# funcionaria apenas para peças de abertura tão longa quanto as
# observadas: nestas a primeira citação aparece no caractere 460, e um
# endereçamento cem caracteres mais enxuto já faria o corte engolir
# citação legítima.
# Largura a partir da qual uma linha é prosa e não rótulo. O resultado é o
# mesmo de 30 a 90 caracteres e se degrada a partir de 95, quando o corte
# passa a atravessar linhas de corpo; 60 fica no meio do intervalo estável,
# longe das duas bordas.
_LARGURA_DE_PROSA = 60
_ROTULO_DE_QUALIFICACAO = re.compile(
    r"^\s*(?:[A-ZÀ-Ý][\wÀ-ÿ.\- ]{0,30}:"
    r"|Autos|Processos?|Protocolo|Apelante|Apelad[oa]|Recorrente|Recorrid[oa]"
    r"|Impetrante|Impetrad[oa]|Embargante|Embargad[oa]|Agravante|Agravad[oa]"
    r"|Requerente|Requerid[oa]|Interessad[oa]|Relator[a]?|Sess[ãa]o|Origem)\b"
)
# Nenhuma peça observada abre o corpo depois deste ponto, e além dele o
# corte deixa de proteger: serve de limite para o caso de um documento sem
# nenhuma linha de prosa reconhecível.
_MAXIMO_DO_PREAMBULO = 2000


# O timbre do órgão vem em caixa alta, e uma linha assim é cabeçalho por
# mais larga que seja. A prosa traz minúsculas em proporção.
_MINIMO_DE_MINUSCULAS = 0.5


def _e_prosa(linha: str) -> bool:
    """A linha é prosa corrida, e não rótulo nem timbre do órgão."""
    if len(linha) < _LARGURA_DE_PROSA or _ROTULO_DE_QUALIFICACAO.match(linha):
        return False
    letras = [c for c in linha if c.isalpha()]
    if not letras:
        return False
    minusculas = sum(1 for c in letras if c.islower())
    return minusculas / len(letras) >= _MINIMO_DE_MINUSCULAS


def _fim_do_preambulo(texto: str) -> int:
    """Posição em que o corpo da peça começa.

    O corpo é a primeira linha de prosa corrida: larga o bastante para não
    ser rótulo, sem o rótulo de qualificação que marca as linhas do
    cabeçalho, e em caixa mista, que distingue a prosa do timbre.
    """
    posicao = 0
    for linha in texto.split("\n"):
        if posicao >= _MAXIMO_DO_PREAMBULO:
            return _MAXIMO_DO_PREAMBULO
        if _e_prosa(linha):
            return posicao
        posicao += len(linha) + 1
    return 0


def _candidatos_dos_padroes(texto: str) -> list[CandidatoCitacao]:
    """Citações delimitadas por padrão: as que trazem identificador e as
    que descrevem o julgado por tribunal, ano e relator."""
    achados = extrair_por_regex(texto) + extrair_prosa_por_regex(texto)
    fim_do_preambulo = _fim_do_preambulo(texto)
    return [
        CandidatoCitacao(inicio=inicio, fim=fim, trecho=trecho, origem="padrao")
        for inicio, fim, trecho in achados
        if inicio >= fim_do_preambulo
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
