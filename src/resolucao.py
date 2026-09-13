# -*- coding: utf-8 -*-
"""
Resolução de citações contra o acervo canônico.

Cada candidato é buscado no acervo, os documentos encontrados são
filtrados para separar quem é o processo citado de quem apenas o menciona,
e a classe resulta da contagem: um único registro é `real`, nenhum é
`inventada`, vários sem critério de desempate é `incompleta`.

A busca é exata, via FTS5 por frase, sem nenhuma etapa de similaridade
semântica — números de processo próximos identificam processos distintos.
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
    posicao: int  # 1-indexed; 0 quando o identificador não foi localizado
    texto: str = ""
    ocorrencia: tuple[int, int] | None = None  # (inicio, fim) 0-indexed


# Um identificador que aparece em dezenas de documentos não distingue um
# processo: é o caso de números curtos, que casam em qualquer parte do
# acervo. Acima deste limite a citação é ambígua por definição.
_MAX_CANDIDATOS_PARA_CLASSIFICAR = 8


def _regex_digitos_com_pontuacao_opcional(identificador: str) -> re.Pattern:
    """Padrão que casa a sequência de dígitos do identificador tolerando
    qualquer pontuação entre eles.

    O FTS5 indexa por token e ignora separadores, de modo que o mesmo
    número pode estar grafado de formas diferentes no texto ("2144995" no
    cabeçalho, "2.144.995" no corpo). Procurar a string exata da busca
    encontraria a ocorrência errada.
    """
    digitos = re.sub(r"\D", "", identificador)
    return re.compile(r"[.\-\s]*".join(digitos))


def _primeira_ocorrencia(texto: str, identificador: str) -> tuple[int, int] | None:
    """Posição (inicio, fim) da primeira ocorrência do identificador no
    texto, em codepoints com fim exclusivo, ou None se ausente."""
    m = _regex_digitos_com_pontuacao_opcional(identificador).search(texto)
    return (m.start(), m.end()) if m else None


def buscar_candidatos(con: sqlite3.Connection, identificador: str) -> list[Candidato]:
    """Documentos do acervo que contêm o identificador, buscados por frase
    no índice FTS5.

    O inteiro teor e a posição da ocorrência acompanham cada candidato,
    porque a etapa seguinte precisa do contexto ao redor do número.
    """
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


# A confiança declarada em cada predição alimenta o bônus de calibração da
# avaliação, que compara a confiança ao acerto efetivo. Ela é uma
# propriedade do caminho que resolveu a citação: um registro único no
# acervo decide por si, enquanto um desempate entre vários candidatos é
# inerentemente menos seguro. Os valores ficam abaixo da certeza absoluta
# porque nenhum caminho é infalível, e um erro declarado como certeza custa
# o dobro no cálculo do bônus.
CONFIANCA_POR_CAMINHO = {
    "normativo": 0.98,        # súmula ou artigo casado no índice normativo
    "sem_identificador": 0.98,  # citação em prosa, sem número a resolver
    "registro_unico": 0.95,   # um só registro do acervo contém o identificador
    "sem_candidato": 0.90,    # nenhum registro contém o identificador
    "desempate": 0.70,        # vários candidatos, resolvidos por posição
    "ambiguo": 0.30,          # identificador presente em documentos demais
}


@dataclass
class Resolucao:
    classe: str
    id_canonico: int | None
    confianca: float

    def __iter__(self):
        """Compatível com o desempacotamento em (classe, id_canonico)."""
        return iter((self.classe, self.id_canonico))


def decidir_classe(candidatos_donos: list[Candidato]) -> tuple[str, int | None]:
    """Classe da citação a partir da quantidade de registros que a
    resolvem: um é `real`, nenhum é `inventada`, vários é `incompleta`."""
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
) -> list[Resolucao]:
    """Classe, id_canonico e confiança de cada candidato, na ordem de
    entrada.

    Súmulas e artigos de lei resolvem pelo índice normativo, que aponta
    para os registros próprios desses dispositivos; buscá-los no FTS
    devolveria os acórdãos que os mencionam. Os demais são buscados pelo
    identificador normalizado. Citações sem identificador — o julgado
    referido apenas por tribunal, ano e relator — são `incompleta`.

    O trabalho determinístico de todos os candidatos é feito primeiro, e
    as perguntas ao LLM seguem numa única chamada em lote.
    """
    from indice_normativo import eh_citacao_normativa, resolver_normativo
    from normalizacao import normalizar_identificadores
    from prompt_dono import classificar_dono_ou_citacao_lote

    resultados: list[Resolucao | None] = [None] * len(candidatos)
    perguntas: list[tuple[str, int, int]] = []
    # Trechos idênticos do acervo compartilham a mesma pergunta.
    indice_por_trecho: dict[tuple[str, int], int] = {}
    cache_busca: dict[str, list[Candidato]] = {}
    pendentes: list[tuple[int, list[int], list[Candidato]]] = []

    for posicao, candidato in enumerate(candidatos):
        if eh_citacao_normativa(candidato.trecho):
            id_normativo = resolver_normativo(indice_normativo, candidato.trecho)
            confianca = CONFIANCA_POR_CAMINHO["normativo"]
            resultados[posicao] = (
                Resolucao("real", id_normativo, confianca)
                if id_normativo is not None
                else Resolucao("inventada", None, confianca)
            )
            continue

        identificadores = normalizar_identificadores(candidato.trecho)
        if not identificadores:
            resultados[posicao] = Resolucao(
                "incompleta", None, CONFIANCA_POR_CAMINHO["sem_identificador"]
            )
            continue

        acervo_do_candidato: list[Candidato] = []
        ambiguo_demais = False
        for identificador in identificadores:
            if identificador not in cache_busca:
                cache_busca[identificador] = buscar_candidatos(con, identificador)
            if len(cache_busca[identificador]) > _MAX_CANDIDATOS_PARA_CLASSIFICAR:
                ambiguo_demais = True
                continue
            acervo_do_candidato.extend(
                # súmulas e dispositivos não têm processo a quem pertencer
                a
                for a in cache_busca[identificador]
                if a.natureza == "acordao" and a.ocorrencia is not None
            )

        # Registro único: não há ambiguidade a resolver.
        distintos = {a.id_canonico for a in acervo_do_candidato}
        if len(distintos) == 1:
            resultados[posicao] = Resolucao(
                "real",
                acervo_do_candidato[0].id_canonico,
                CONFIANCA_POR_CAMINHO["registro_unico"],
            )
            continue

        indices_perguntas: list[int] = []
        candidatos_acervo: list[Candidato] = []
        for achado in acervo_do_candidato:
            chave = (achado.documento_id, achado.ocorrencia[0])
            if chave not in indice_por_trecho:
                indice_por_trecho[chave] = len(perguntas)
                perguntas.append((achado.texto, *achado.ocorrencia))
            indices_perguntas.append(indice_por_trecho[chave])
            candidatos_acervo.append(achado)

        if not indices_perguntas:
            # Sem candidatos classificáveis: o identificador ambíguo indica
            # que o número existe no acervo mas não identifica um registro.
            resultados[posicao] = (
                Resolucao("incompleta", None, CONFIANCA_POR_CAMINHO["ambiguo"])
                if ambiguo_demais
                else Resolucao("inventada", None, CONFIANCA_POR_CAMINHO["sem_candidato"])
            )
        else:
            pendentes.append((posicao, indices_perguntas, candidatos_acervo))

    respostas = classificar_dono_ou_citacao_lote(qwen, perguntas)

    for posicao, indices_perguntas, candidatos_acervo in pendentes:
        donos = [
            acervo
            for indice_pergunta, acervo in zip(indices_perguntas, candidatos_acervo)
            if respostas[indice_pergunta]
        ]
        # A posição do identificador desempata: o processo traz o próprio
        # número na abertura, enquanto quem o cita o traz no corpo.
        if not donos:
            donos = [min(candidatos_acervo, key=lambda c: c.posicao)]

        unicos = {c.id_canonico: c for c in donos}
        classe, id_canonico = decidir_classe(list(unicos.values()))
        if classe == "incompleta":
            vencedor = min(unicos.values(), key=lambda c: c.posicao)
            classe, id_canonico = "real", vencedor.id_canonico
        resultados[posicao] = Resolucao(
            classe, id_canonico, CONFIANCA_POR_CAMINHO["desempate"]
        )

    if any(r is None for r in resultados):
        raise AssertionError("todo candidato deve receber uma classe")
    return resultados


def resolver_citacao(
    con: sqlite3.Connection,
    qwen,
    indice_normativo: dict[tuple[str, ...], int],
    candidato,
) -> Resolucao:
    """Resolve um único candidato. Para um documento inteiro, prefira
    `resolver_citacoes`, que agrupa as chamadas ao LLM."""
    return resolver_citacoes(con, qwen, indice_normativo, [candidato])[0]
