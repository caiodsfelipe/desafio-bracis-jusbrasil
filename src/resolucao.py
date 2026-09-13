"""
Resolução de citações contra o acervo canônico.

Cada candidato é buscado no acervo, os documentos encontrados são
filtrados para separar quem é o processo citado de quem apenas o menciona,
e a classe resulta da contagem: um único registro é `real`, nenhum é
`inventada`, vários sem critério de desempate é `incompleta`.

A busca é exata, via FTS5 por frase, sem nenhuma etapa de similaridade
semântica: números de processo próximos identificam processos distintos.
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

# Um acórdão traz o próprio número no cabeçalho, junto da data, do órgão
# julgador e das partes; quem apenas o cita traz o número no corpo do voto,
# milhares de caracteres adiante. O cabeçalho varia de tamanho entre os
# tribunais, e no TST a autuação alcança mil e cem caracteres; o limite
# acomoda o mais longo deles. Medido sobre o acervo, o identificador do
# processo dono aparece antes deste ponto em 76 dos 77 casos, contra 3 dos
# 24 dos documentos que só o mencionam.
_LIMITE_CABECALHO = 2000

# O acervo guarda o mesmo acórdão mais de uma vez, com diferenças de
# digitalização que não mudam o conteúdo. Nesses pares o identificador cai
# na mesma posição dos dois textos, e nenhum critério textual os separa: a
# escolha precisa apenas ser estável, e recai sobre o menor id_canonico.
_TOLERANCIA_POSICAO_DUPLICATA = 2


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


def contar_candidatos(con: sqlite3.Connection, identificador: str) -> int:
    """Quantos documentos do acervo contêm o identificador.

    A contagem precede a leitura porque um número curto casa com centenas
    de documentos, e carregar o inteiro teor de todos eles para descartá-los
    em seguida custa dezenas de megabytes por citação.
    """
    (total,) = con.execute(
        "SELECT count(*) FROM documentos_fts WHERE documentos_fts MATCH ?",
        (f'"{identificador}"',),
    ).fetchone()
    return total


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


# A confiança é uma propriedade do caminho que resolveu a citação, calibrada
# pela taxa de acerto que o caminho apresenta. Os valores ficam abaixo da
# certeza absoluta porque nenhum caminho é infalível, e um erro declarado
# como certeza custa o dobro no cálculo do bônus; mas rebaixá-los além da
# taxa observada também custa, porque o bônus mede a distância entre a
# confiança declarada e o acerto efetivo. Dois caminhos podem partilhar o
# mesmo valor quando acertam na mesma medida: é o caminho que a `Resolucao`
# carrega, não a confiança, que identifica a origem da decisão.
CONFIANCA_POR_CAMINHO = {
    "normativo": 0.98,        # súmula ou artigo casado no índice normativo
    "sem_identificador": 0.98,  # citação em prosa, sem número a resolver
    "registro_unico": 0.97,   # um só registro do acervo contém o identificador
    "sem_candidato": 0.96,    # nenhum registro contém o identificador
    "cabecalho": 0.95,        # um só registro traz o identificador no cabeçalho
    "desempate": 0.75,        # vários registros, separados pelo modelo
    "so_mencionado": 0.60,    # o número só aparece citado, nunca como autuação
    "ambiguo": 0.30,          # identificador presente em documentos demais
}


@dataclass
class Resolucao:
    classe: str
    id_canonico: int | None
    confianca: float
    caminho: str

    def __iter__(self):
        """Compatível com o desempacotamento em (classe, id_canonico)."""
        return iter((self.classe, self.id_canonico))


def resolvido_por(caminho: str, classe: str, id_canonico: int | None = None) -> Resolucao:
    """Resolução anotada com o caminho que a produziu, de onde vem a
    confiança declarada."""
    return Resolucao(classe, id_canonico, CONFIANCA_POR_CAMINHO[caminho], caminho)


def _ordem_de_preferencia(candidato: Candidato) -> tuple[int, int]:
    """Chave de ordenação dos candidatos: primeiro quem traz o
    identificador mais perto do início, e o id_canonico torna a escolha
    estável entre registros equivalentes."""
    return (candidato.posicao, candidato.id_canonico)


def _um_por_registro(candidatos: list[Candidato]) -> list[Candidato]:
    """Um candidato por id_canonico, o de identificador mais adiantado."""
    por_registro: dict[int, Candidato] = {}
    for candidato in candidatos:
        atual = por_registro.get(candidato.id_canonico)
        if atual is None or _ordem_de_preferencia(candidato) < _ordem_de_preferencia(atual):
            por_registro[candidato.id_canonico] = candidato
    return sorted(por_registro.values(), key=_ordem_de_preferencia)


def _desempatar_por_posicao(candidatos: list[Candidato]) -> "Resolucao | None":
    """Resolve a citação pela posição do identificador nos registros
    encontrados, e devolve None quando a posição não decide.

    Um registro só responde pela citação se traz o número no próprio
    cabeçalho. Havendo um único assim, é ele o processo citado. Havendo
    vários que o trazem na mesma posição, são cópias do mesmo acórdão no
    acervo e qualquer uma responde pela citação.

    Quando nenhum registro traz o número no cabeçalho, o número aparece no
    acervo apenas dentro de fundamentações, é citado e nunca autuado, e
    não existe processo com ele: a citação é inventada. É o que distingue
    uma referência a processo inexistente de uma referência legítima, já
    que ambas encontram documentos na busca por texto.
    """
    ordenados = _um_por_registro(candidatos)
    no_cabecalho = [c for c in ordenados if c.posicao < _LIMITE_CABECALHO]
    if not no_cabecalho:
        return resolvido_por("so_mencionado", "inventada")

    primeiro = no_cabecalho[0]
    duplicatas = [
        c
        for c in no_cabecalho
        if abs(c.posicao - primeiro.posicao) <= _TOLERANCIA_POSICAO_DUPLICATA
    ]
    if len(duplicatas) > 1:
        return resolvido_por(
            "registro_unico", "real", min(c.id_canonico for c in duplicatas)
        )
    if len(no_cabecalho) == 1:
        return resolvido_por("cabecalho", "real", primeiro.id_canonico)
    return None


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
    identificador normalizado. Citações sem identificador, o julgado
    referido apenas por tribunal, ano e relator, são `incompleta`.

    O trabalho determinístico de todos os candidatos é feito primeiro, e
    as perguntas ao LLM seguem numa única chamada em lote.
    """
    from indice_normativo import eh_citacao_normativa, resolver_normativo
    from normalizacao import normalizar_identificadores
    from prompt_dono import NENHUMA, escolher_registro_lote

    resultados: list[Resolucao | None] = [None] * len(candidatos)
    disputas: list[tuple[str, list[str]]] = []
    # Um identificador que casa com documentos demais é registrado como None,
    # e o acervo não chega a ser lido para ele.
    cache_busca: dict[str, list[Candidato] | None] = {}
    pendentes: list[tuple[int, list[Candidato]]] = []

    for posicao, candidato in enumerate(candidatos):
        if eh_citacao_normativa(candidato.trecho):
            id_normativo = resolver_normativo(indice_normativo, candidato.trecho)
            resultados[posicao] = (
                resolvido_por("normativo", "real", id_normativo)
                if id_normativo is not None
                else resolvido_por("normativo", "inventada")
            )
            continue

        identificadores = normalizar_identificadores(candidato.trecho)
        if not identificadores:
            resultados[posicao] = resolvido_por("sem_identificador", "incompleta")
            continue

        acervo_do_candidato: list[Candidato] = []
        ambiguo_demais = False
        for identificador in identificadores:
            if identificador not in cache_busca:
                if contar_candidatos(con, identificador) > _MAX_CANDIDATOS_PARA_CLASSIFICAR:
                    cache_busca[identificador] = None
                else:
                    cache_busca[identificador] = buscar_candidatos(con, identificador)
            if cache_busca[identificador] is None:
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
            resultados[posicao] = resolvido_por(
                "registro_unico", "real", acervo_do_candidato[0].id_canonico
            )
            continue

        if not acervo_do_candidato:
            # Sem candidatos classificáveis: o identificador ambíguo indica
            # que o número existe no acervo mas não identifica um registro.
            resultados[posicao] = (
                resolvido_por("ambiguo", "incompleta")
                if ambiguo_demais
                else resolvido_por("sem_candidato", "inventada")
            )
            continue

        resolucao = _desempatar_por_posicao(acervo_do_candidato)
        if resolucao is not None:
            resultados[posicao] = resolucao
            continue

        # Vários processos foram autuados com o mesmo número e diferem na
        # espécie do recurso; só a leitura dos cabeçalhos os separa.
        em_disputa = _um_por_registro(acervo_do_candidato)
        disputas.append((candidato.trecho, [a.texto for a in em_disputa]))
        pendentes.append((posicao, em_disputa))

    escolhas = escolher_registro_lote(qwen, disputas)

    for (posicao, em_disputa), escolha in zip(pendentes, escolhas, strict=True):
        # O modelo recusou todas: o número consta do acervo apenas em
        # fundamentações, e nenhum processo responde por ele.
        resultados[posicao] = (
            resolvido_por("so_mencionado", "inventada")
            if escolha == NENHUMA
            else resolvido_por("desempate", "real", em_disputa[escolha].id_canonico)
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
