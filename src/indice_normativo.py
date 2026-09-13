# -*- coding: utf-8 -*-
"""
Índice dos 18 registros normativos do acervo (5 súmulas + 13 dispositivos
de lei), construído uma vez e consultado por chave.

Por que um índice à parte: súmulas e dispositivos NÃO resolvem pelo mesmo
caminho dos acórdãos. Buscar "Súmula 83 do STJ" no FTS devolve dezenas de
acórdãos que a mencionam — nenhum deles é a súmula. Os registros de
natureza sumula/dispositivo existem para ser o alvo da resolução, e são
poucos o bastante para carregar em memória e casar por número.

Como o número é obtido (nenhum hardcode do goldenset — tudo derivado do
acervo):
- Dispositivos: o texto começa com "Art. N." — basta ler o número.
- Súmulas: 3 das 5 trazem o número no rodapé do próprio enunciado, no
  formato "(SÚMULA 443, TERCEIRA SEÇÃO, julgado em ...)". Para as 2 que
  não trazem (STF e TST), o número é derivado por votação: procura-se o
  enunciado citado dentro de acórdãos do acervo e lê-se o número que
  aparece imediatamente antes da citação ("Súmula 331 do TST, ...").
"""
import re
import sqlite3
from collections import Counter

_NUM_SUMULA_NO_TEXTO = re.compile(
    r"S[ÚU]MULA\s+(?:VINCULANTE\s+)?(?:n[º°.]?\s*)?(\d{1,3})", re.IGNORECASE
)
_NUM_SUMULA_CITADA = re.compile(
    r"S[úu]mula\s+(?:Vinculante\s+)?(?:n[º°.]?\s*)?(\d{1,3})", re.IGNORECASE
)
_NUM_ARTIGO = re.compile(r"^\s*Art(?:igo)?\.?\s*(\d{1,4})", re.IGNORECASE)

# Gatilhos usados para LER a citação no documento de entrada (não o acervo).
# Toleram o ruído de OCR do nível 2 na própria palavra-gatilho: o goldenset
# traz "5úmula 211 do STJ" (S->5) e "Súm. 166 do TSE" (abreviada). O ruído
# no número em si é tratado em normalizacao.py; aqui é só na palavra.
_CITACAO_SUMULA = re.compile(
    r"[S5]["
    r"úuÚU]m(?:ula)?\.?\s+(?:Vinculante\s+)?(?:n[º°.]?\s*)?(\d{1,3})",
    re.IGNORECASE,
)
# captura o número COM eventual ponto de milhar ("art. 1.134" -> "1.134"),
# senão "1.134" seria lido como "1" e casaria com o art. 1º da LC 64
_CITACAO_ARTIGO = re.compile(r"art(?:igo)?\.?\s*(\d{1,3}(?:\.\d{3})*)", re.IGNORECASE)

_PALAVRAS_POR_JANELA = 8
_JANELAS_POR_SUMULA = 6
_CONTEXTO_ANTES = 150


def _janelas(texto: str):
    """Fatias do enunciado usadas como chave de busca por frase. Várias
    janelas ao longo do texto, para não depender de acertar onde termina o
    cabeçalho temático em caixa alta."""
    palavras = " ".join(texto.split()).split()
    limite = min(len(palavras) - _PALAVRAS_POR_JANELA, _JANELAS_POR_SUMULA * _PALAVRAS_POR_JANELA)
    for i in range(0, max(limite, 1), _PALAVRAS_POR_JANELA):
        yield " ".join(palavras[i : i + _PALAVRAS_POR_JANELA])


def _numero_por_citacoes(con: sqlite3.Connection, texto_sumula: str) -> str | None:
    """Deriva o número da súmula lendo o que a precede quando ela é citada
    em acórdãos do acervo. Votação: o número mais frequente vence."""
    votos = Counter()
    for chave in _janelas(texto_sumula):
        try:
            linhas = con.execute(
                "SELECT d.texto FROM documentos_fts JOIN documentos d"
                " ON d.rowid = documentos_fts.rowid WHERE documentos_fts MATCH ?",
                (f'"{chave}"',),
            ).fetchall()
        except sqlite3.OperationalError:
            continue  # chave com caractere que o FTS rejeita
        for (texto_doc,) in linhas:
            normalizado = " ".join(texto_doc.split())
            for ocorrencia in re.finditer(re.escape(chave), normalizado):
                antes = normalizado[max(0, ocorrencia.start() - _CONTEXTO_ANTES) : ocorrencia.start()]
                votos.update(_NUM_SUMULA_CITADA.findall(antes))
    return votos.most_common(1)[0][0] if votos else None


# O número do artigo sozinho não identifica o dispositivo: o art. 290 do
# acervo é do Código Penal Militar, e o goldenset traz "art 290 da
# Constituição Federal" como `inventada`. O diploma precisa bater.
#
# Os textos do acervo não nomeiam o próprio diploma, então ele é derivado
# de palavras características do conteúdo de cada artigo (cada tupla é
# casada contra o texto do registro; a primeira que casar vence).
_MARCAS_DE_DIPLOMA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("codigo_eleitoral", ("Tribunais Regionais são terminativas",)),
    ("codigo_penal_militar", ("ainda que gratuitamente, ter em depósito",)),
    ("cdc", ("fornecedor de serviços responde",)),
    ("constituicao", ("Estatuto da Magistratura", "direitos dos trabalhadores urbanos", "Todos são iguais perante a lei")),
    ("clt", ("Recurso de Revista para Turma", "ônus da prova incumbe: (Redação dada", "extinção do contrato de trabalho")),
    ("cpp", ("prisão preventiva poderá ser decretada",)),
    ("codigo_civil", ("por ação ou omissão voluntária",)),
    ("lc64", ("São inelegíveis: I - para qualquer cargo",)),
    ("cpc", ("ônus da prova incumbe: I - ao autor",)),
)

# Como o diploma é escrito nas citações (goldenset): nome por extenso,
# sigla, ou o número da lei que o instituiu.
_DIPLOMA_NA_CITACAO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cpc", ("código de processo civil", "cpc", "13.105", "13105")),
    ("cpp", ("código de processo penal", "cpp")),
    ("codigo_penal_militar", ("código penal militar", "cpm")),
    ("cdc", ("código de defesa do consumidor", "cdc", "8.078", "8078")),
    ("clt", ("consolidação das leis do trabalho", "clt", "13.467", "13467")),
    ("codigo_eleitoral", ("código eleitoral", "4.737", "4737")),
    ("codigo_civil", ("código civil", "10.406", "10406")),
    ("lc64", ("lei complementar nº 64", "lei complementar 64", "lc 64", "64/1990")),
    ("constituicao", ("constituição", "cf/88", "carta magna", "constituição da república")),
)


def _diploma_do_registro(texto: str) -> str | None:
    normalizado = " ".join(texto.split())
    for diploma, marcas in _MARCAS_DE_DIPLOMA:
        if any(marca in normalizado for marca in marcas):
            return diploma
    return None


def _diploma_da_citacao(trecho: str) -> str | None:
    normalizado = " ".join(trecho.split()).lower()
    for diploma, apelidos in _DIPLOMA_NA_CITACAO:
        if any(apelido in normalizado for apelido in apelidos):
            return diploma
    return None


def construir_indice(con: sqlite3.Connection) -> dict[tuple[str, ...], int]:
    """Mapa de chave -> id_canonico. Súmulas: ("sumula", numero).
    Dispositivos: ("artigo", numero, diploma) — o diploma faz parte da
    chave porque o mesmo número de artigo existe em diplomas diferentes."""
    indice: dict[tuple[str, ...], int] = {}
    for id_canonico, natureza, texto in con.execute(
        "SELECT id, natureza, texto FROM documentos WHERE natureza IN ('sumula', 'dispositivo')"
    ):
        if natureza == "dispositivo":
            achado = _NUM_ARTIGO.match(texto)
            diploma = _diploma_do_registro(texto)
            if achado and diploma:
                indice[("artigo", achado.group(1), diploma)] = id_canonico
            continue
        numeros = _NUM_SUMULA_NO_TEXTO.findall(" ".join(texto.split()))
        numero = numeros[0] if numeros else _numero_por_citacoes(con, texto)
        if numero:
            indice[("sumula", numero)] = id_canonico
    return indice


def eh_citacao_normativa(trecho: str) -> bool:
    """O trecho cita uma súmula ou um artigo de lei? Independe de o
    registro existir na cobertura — serve para o roteamento: uma citação
    normativa que não resolve é `inventada`, e NÃO deve seguir para a
    busca de acórdão no FTS (onde o número solto casaria em qualquer
    documento que o mencione)."""
    return bool(_CITACAO_SUMULA.search(trecho) or _CITACAO_ARTIGO.search(trecho))


def resolver_normativo(indice: dict[tuple[str, ...], int], trecho: str) -> int | None:
    """id_canonico do registro normativo citado no trecho, ou None se o
    trecho não for citação de súmula/artigo, ou se o registro não estiver
    na cobertura congelada — inclusive quando o número existe mas em outro
    diploma (nesse caso a citação é `inventada`, decidido por quem chama)."""
    achado = _CITACAO_SUMULA.search(trecho)
    if achado:
        return indice.get(("sumula", achado.group(1)))
    achado = _CITACAO_ARTIGO.search(trecho)
    if achado:
        numero = achado.group(1).replace(".", "")  # "1.134" -> "1134"
        diploma = _diploma_da_citacao(trecho)
        if diploma:
            return indice.get(("artigo", numero, diploma))
    return None
