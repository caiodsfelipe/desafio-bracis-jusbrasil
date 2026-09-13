# -*- coding: utf-8 -*-
"""
Normalização do identificador numérico dentro de um span já identificado
como citação (ROI local — nunca aplicada ao documento inteiro).

Mapeamento letra->dígito validado empiricamente contra o goldenset (ver
memória do projeto): O/o->0, l/I->1, S/s->5, G->6, g->9. Uma letra só é
tratada como dígito disfarçado quando está imediatamente colada (sem
espaço) a pelo menos um dígito real dentro do mesmo bloco — isso evita
confundir sigla pura (ex. "RESP", só letras) com número disfarçado
(ex. "21737l8", letra colada a dígitos).

Números CNJ (e variantes menores) já vêm com pontuação própria no texto
(traços/pontos separando sequencial-DV.ano.segmento.tribunal.origem) — o
FTS5 casa essa pontuação bem como está (cada segmento vira um token).
Reagrupar do zero destruiria essa estrutura. Por isso: bloco com pontuação
própria -> só traduz letra->dígito, preserva a pontuação; bloco sem
nenhuma pontuação (sequência crua) -> reagrupa de 3 em 3, que é a forma
de separador de milhar usada no acervo.
"""
import re

MAPA_OCR = {
    "O": "0", "o": "0",
    "l": "1", "I": "1",
    "S": "5", "s": "5",
    "G": "6",
    "g": "9",
}

_CHARS_NUMERICOS = "0-9OolIGgSs"

# bloco: dígitos/letras-disfarçadas, podendo ter pontuação (. ou -) ou
# espaço ENTRE dois caracteres numéricos — não no início/fim, para não
# engolir a pontuação/palavras de fora da citação. Espaço entra como cola
# válida porque o nível 2 usa espaço solto como separador de milhar
# ruidoso (ex. "1 307 026", "1. 570.531") — sem isso, cada pedaço vira um
# bloco separado e minúsculo, que também casa em qualquer parte do banco.
#
# Mas hífen com espaço DOS DOIS LADOS ("21737l8 - SP") é o padrão de
# separador antes da UF, não separador de milhar — nunca cola nesse caso,
# senão o sufixo UF gruda no número (a letra da UF passa a ser lida como
# dígito disfarçado, já que está na lista de confusões OCR).
_UNIDADE_NUMERICA = rf"[{_CHARS_NUMERICOS}]"
_COLA = rf"(?:{_UNIDADE_NUMERICA}|\.|-(?!\s)(?<!\s-)| )"
_BLOCO_CANDIDATO = re.compile(
    rf"{_UNIDADE_NUMERICA}(?:{_COLA}*{_UNIDADE_NUMERICA})?"
)


def _aparar_letras_isoladas(bloco: str) -> str:
    """Corta das bordas do bloco qualquer letra do MAPA_OCR que não esteja
    colada a um dígito real — ela não faz parte do número, é ruído que
    grudou na extração (ex. o "O" de "REG." antes de "76.532", separado
    por espaço: o bloco bruto "O 76.532" vira "76.532"). Repete até a
    borda ser um dígito real ou uma letra já colada a um."""
    def eh_letra_isolada(i: int) -> bool:
        if bloco[i] not in MAPA_OCR:
            return False
        anterior = bloco[i - 1] if i > 0 else ""
        seguinte = bloco[i + 1] if i + 1 < len(bloco) else ""
        return not (anterior.isdigit() or seguinte.isdigit())

    inicio, fim = 0, len(bloco)
    while inicio < fim and eh_letra_isolada(inicio):
        inicio += 1
    while fim > inicio and eh_letra_isolada(fim - 1):
        fim -= 1
    return bloco[inicio:fim]


def _traduzir_letras(bloco: str) -> str:
    """Traduz uma letra do MAPA_OCR só quando ela está imediatamente
    colada (sem espaço) a pelo menos um dígito real — nunca quando está
    isolada (cercada por espaço/pontuação/borda do bloco). Sem essa
    checagem posição a posição, uma letra solta que sobrou perto de um
    número por coincidência (ex. o "O" de "REG." antes de "76.532", com
    espaço entre eles) seria lida como dígito disfarçado."""
    resultado = []
    for i, ch in enumerate(bloco):
        if ch in MAPA_OCR:
            anterior = bloco[i - 1] if i > 0 else ""
            seguinte = bloco[i + 1] if i + 1 < len(bloco) else ""
            colada_a_digito = anterior.isdigit() or seguinte.isdigit()
            resultado.append(MAPA_OCR[ch] if colada_a_digito else ch)
        else:
            resultado.append(ch)
    return "".join(resultado)


def _reagrupar(digitos: str) -> str:
    """'2173718' -> '2.173.718' (agrupa de 3 em 3 a partir da direita).
    Espera receber só dígitos — quem chama remove espaço/pontuação antes."""
    partes = []
    while digitos:
        partes.append(digitos[-3:])
        digitos = digitos[:-3]
    return ".".join(reversed(partes))


def _normalizar_bloco(bloco: str) -> str:
    bloco = _aparar_letras_isoladas(bloco)
    tem_pontuacao_propria = any(c in ".-" for c in bloco)
    traduzido = _traduzir_letras(bloco)
    if tem_pontuacao_propria:
        # espaço aqui é sempre ruído de digitação (nunca separador de
        # milhar intencional quando já há ponto/traço estruturando o
        # número) — remove, preserva o resto da pontuação como está
        return traduzido.replace(" ", "").replace("\xa0", "")
    # sem pontuação própria: espaço solto é separador de milhar ruidoso
    # (ex. "1 307 026") — remove tudo e reagrupa do zero
    so_digitos = re.sub(r"\D", "", traduzido)
    return _reagrupar(so_digitos)


# Ano precedido de preposição ("de 2024", "em 2023") é data do julgado, não
# identificador — mesma regra já validada na extração por regex. Sem isso,
# uma citação em prosa ("julgado do STF de 2024, relator X"), que não tem
# identificador algum e deve ser `incompleta`, devolveria "2.024" e seria
# buscada no FTS como se fosse número de processo.
_PREPOSICAO_ANO = re.compile(r"\b(?:de|em)\s+((?:19|20)\d{2})\b", re.IGNORECASE)


def normalizar_identificadores(span: str) -> list[str]:
    """Extrai e normaliza cada bloco numérico do span, um por vez (não
    concatena blocos distintos — um span pode ter mais de um número
    relevante, ex. "Súmula 331 do TST" tem só um bloco, mas alguns rótulos
    trazem número de processo E ano em blocos separados por texto).
    Lista vazia = span sem identificador buscável (prosa livre, ou só um
    ano de julgamento)."""
    anos_de_julgado = set(_PREPOSICAO_ANO.findall(span))
    blocos = _BLOCO_CANDIDATO.findall(span)
    identificadores = []
    for bloco in blocos:
        if not any(c.isdigit() for c in bloco):
            continue
        normalizado = _normalizar_bloco(bloco)
        if normalizado.replace(".", "") in anos_de_julgado:
            continue
        identificadores.append(normalizado)
    return identificadores
