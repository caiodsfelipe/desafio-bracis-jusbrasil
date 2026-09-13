# -*- coding: utf-8 -*-
"""
Resolução: busca no acervo canônico, distinção "dono do processo" vs
"só cita o processo", e decisão de classe por contagem de candidatos.

Retrieve-then-verify, não RAG semântico: busca exata via FTS5 (por frase,
já que unicode61 tokeniza em separadores) + regra de posição no texto, sem
nenhuma etapa de similaridade/embedding.
"""
import re
import sqlite3
from dataclasses import dataclass


@dataclass
class Candidato:
    documento_id: str
    id_canonico: int
    tribunal: str | None
    natureza: str
    posicao: int  # 1-indexed, 0 = não encontrado (convenção do instr() do SQLite)
    texto: str = ""  # inteiro teor, já trazido pela consulta que achou o candidato
    ocorrencia: tuple[int, int] | None = None  # (inicio, fim) 0-indexed do identificador


# Distinção "documento é o dono do processo" vs "só cita o processo":
# NÃO é regra manual nem limiar de posição absoluta. Duas tentativas
# descartadas (ver memória do projeto):
# 1. Limiar de posição absoluta — documentos do TST têm o próprio número
#    de processo aparecendo a dezenas de milhares de caracteres do início
#    (cabeçalho começa com ementa/tese jurídica extensa), não nos
#    primeiros ~100 caracteres como STF/STJ/STM/TSE.
# 2. Regra textual "RELATOR próximo" — validada a 100% em teste isolado,
#    mas com falsos positivos sistemáticos no teste end-to-end: citações
#    de precedentes DENTRO do corpo de outros acórdãos também mencionam
#    "relator" perto do número (é a forma padrão como juristas citam
#    jurisprudência: "REsp X, relator Ministro Y, Turma, julgado em..."),
#    então "relator próximo" sozinho não distingue cabeçalho de citação.
#    Tentar refinar com mais sinais textuais (maiúscula+dois-pontos vs
#    minúscula+parênteses) foi descartado por ser mais uma calibração
#    frágil na mesma linha.
#
# Decisão: delegar ao LLM (Qwen3-8B) como pergunta fechada de classificação
# sobre um contexto já delimitado — não há risco de alucinação aqui (não
# há span para inventar, só um julgamento contextual sobre texto que já
# existe). Ver prompt_dono.py (define a janela de contexto usada).


def _regex_digitos_com_pontuacao_opcional(identificador: str) -> re.Pattern:
    """FTS5 tokeniza em separadores — a mesma citação pode aparecer no
    texto com pontuação diferente da usada na busca (ex.: "2144995" no
    cabeçalho vs "2.144.995" no corpo). instr() com a string exata da
    busca acharia a ocorrência errada. Em vez disso, buscamos a sequência
    de dígitos permitindo qualquer pontuação (ou nenhuma) entre eles."""
    digitos = re.sub(r"\D", "", identificador)
    return re.compile(r"[.\-\s]*".join(digitos))


def _primeira_ocorrencia(texto: str, identificador: str) -> tuple[int, int] | None:
    """(inicio, fim) em codepoints, 0-indexed, fim exclusivo — da primeira
    ocorrência real do identificador no texto, tolerando qualquer
    pontuação entre os dígitos. None se não encontrado."""
    m = _regex_digitos_com_pontuacao_opcional(identificador).search(texto)
    return (m.start(), m.end()) if m else None


def buscar_candidatos(con: sqlite3.Connection, identificador: str) -> list[Candidato]:
    """Busca no FTS5, por frase, todos os documentos que contêm o
    `identificador` (já normalizado — ver normalizacao.py). A posição
    reportada é a da PRIMEIRA ocorrência real no texto (ver
    `_primeira_ocorrencia`), não a de instr() com a string exata da busca.

    Guarda `texto` e `ocorrencia` no Candidato: quem for classificar
    dono/citação precisa do contexto ao redor do identificador, e sem isso
    faria um SELECT extra por candidato para reler o mesmo documento que
    esta consulta já trouxe.

    Não filtra ainda por "é dono" — isso depende do LLM e é feito em lote
    por `resolver_citacoes`."""
    cur = con.execute(
        """
        SELECT d.documento_id, d.id, d.tribunal, d.natureza, d.texto
        FROM documentos_fts
        JOIN documentos d ON d.rowid = documentos_fts.rowid
        WHERE documentos_fts MATCH ?
        """,
        (f'"{identificador}"',),
    )
    candidatos = []
    for documento_id, id_canonico, tribunal, natureza, texto in cur.fetchall():
        ocorrencia = _primeira_ocorrencia(texto, identificador)
        candidatos.append(
            Candidato(
                documento_id=documento_id,
                id_canonico=id_canonico,
                tribunal=tribunal,
                natureza=natureza,
                posicao=ocorrencia[0] + 1 if ocorrencia else 0,
                texto=texto,
                ocorrencia=ocorrencia,
            )
        )
    return candidatos


def decidir_classe(candidatos_donos: list[Candidato]) -> tuple[str, int | None]:
    """Contagem de candidatos -> classe (ver contrato do desafio):
    exatamente 1 -> real (com id_canonico); 0 -> inventada;
    2+ sem critério de desempate -> incompleta."""
    if len(candidatos_donos) == 1:
        return "real", candidatos_donos[0].id_canonico
    if len(candidatos_donos) == 0:
        return "inventada", None
    return "incompleta", None


def resolver_citacoes(
    con: sqlite3.Connection,
    qwen,
    indice_normativo: dict[tuple[str, ...], int],
    candidatos: list,
) -> list[tuple[str, int | None]]:
    """Resolve TODOS os candidatos de um documento em (classe, id_canonico),
    na mesma ordem em que entraram.

    Trabalha em duas fases para não pagar latência à toa: primeiro tudo
    que é determinístico (roteamento normativo e buscas no FTS), juntando
    as perguntas de dono/citação de todos os candidatos; depois UMA
    chamada em lote ao LLM; então a decisão de classe. Resolver candidato
    a candidato faria dezenas de inferências sequenciais cujo custo é
    quase todo overhead — a resposta útil tem 1 token.

    Roteamento (os dois caminhos são distintos por natureza do alvo):
    - súmula/artigo de lei -> índice normativo (18 registros próprios,
      casados por número + diploma). Buscar esses no FTS devolveria os
      acórdãos que os mencionam, nunca o registro em si.
    - acórdão -> FTS pelo identificador normalizado + filtro "é o dono do
      processo" (LLM) + contagem.
    Citação sem identificador buscável (prosa: "julgado do STF de 2024,
    relator X") é `incompleta` sem passar pelo banco — buscável por
    metadados, mas casaria com dezenas de acórdãos, sem desempate."""
    from indice_normativo import eh_citacao_normativa, resolver_normativo
    from normalizacao import normalizar_identificadores
    from prompt_dono import classificar_dono_ou_citacao_lote

    resultados: list[tuple[str, int | None] | None] = [None] * len(candidatos)
    perguntas: list[tuple[str, int, int]] = []  # (texto, inicio, fim) para o LLM
    # (documento_id, inicio) -> índice em `perguntas`. Duas citações do mesmo
    # documento de entrada costumam cair no mesmo trecho do acervo (e o mesmo
    # documento reaparece para identificadores diferentes): sem isso, a mesma
    # pergunta iria várias vezes ao LLM.
    indice_por_trecho: dict[tuple[str, int], int] = {}
    # identificador -> resultado do FTS, para não repetir a consulta
    cache_busca: dict[str, list[Candidato]] = {}
    # para cada candidato, os índices de `perguntas` que lhe pertencem e o
    # Candidato do acervo correspondente a cada pergunta
    pendentes: list[tuple[int, list[int], list[Candidato]]] = []

    for posicao, candidato in enumerate(candidatos):
        if eh_citacao_normativa(candidato.trecho):
            id_normativo = resolver_normativo(indice_normativo, candidato.trecho)
            # citação normativa que não resolve é `inventada` e para aqui: o
            # número de uma súmula/artigo inexistente casaria no FTS com
            # qualquer acórdão que mencione aquele número
            resultados[posicao] = (
                ("real", id_normativo) if id_normativo is not None else ("inventada", None)
            )
            continue

        identificadores = normalizar_identificadores(candidato.trecho)
        if not identificadores:
            resultados[posicao] = ("incompleta", None)
            continue

        indices_perguntas: list[int] = []
        candidatos_acervo: list[Candidato] = []
        for identificador in identificadores:
            if identificador not in cache_busca:
                cache_busca[identificador] = buscar_candidatos(con, identificador)
            for achado in cache_busca[identificador]:
                # súmulas/dispositivos não têm "dono de processo" — só
                # acórdãos passam pela classificação
                if achado.natureza != "acordao" or achado.ocorrencia is None:
                    continue
                chave = (achado.documento_id, achado.ocorrencia[0])
                if chave not in indice_por_trecho:
                    indice_por_trecho[chave] = len(perguntas)
                    perguntas.append((achado.texto, *achado.ocorrencia))
                indices_perguntas.append(indice_por_trecho[chave])
                candidatos_acervo.append(achado)

        if not indices_perguntas:
            resultados[posicao] = ("inventada", None)
        else:
            pendentes.append((posicao, indices_perguntas, candidatos_acervo))

    respostas = classificar_dono_ou_citacao_lote(qwen, perguntas)

    for posicao, indices_perguntas, candidatos_acervo in pendentes:
        donos = [
            acervo
            for indice_pergunta, acervo in zip(indices_perguntas, candidatos_acervo)
            if respostas[indice_pergunta]
        ]
        unicos = {c.id_canonico: c for c in donos}
        resultados[posicao] = decidir_classe(list(unicos.values()))

    if any(r is None for r in resultados):
        raise AssertionError("candidato sem resultado — todo caminho deve decidir uma classe")
    return resultados


def resolver_citacao(
    con: sqlite3.Connection,
    qwen,
    indice_normativo: dict[tuple[str, ...], int],
    candidato,
) -> tuple[str, int | None]:
    """Um candidato só. Prefira `resolver_citacoes` para um documento
    inteiro — esta versão faz uma chamada isolada ao LLM por candidato."""
    return resolver_citacoes(con, qwen, indice_normativo, [candidato])[0]
