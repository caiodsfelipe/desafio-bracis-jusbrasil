"""
Índice dos registros normativos do acervo, as súmulas e os dispositivos de
lei, construído uma vez e consultado por chave.

Esses registros não resolvem pelo mesmo caminho dos acórdãos: buscar
"Súmula 83 do STJ" no índice de texto devolve os acórdãos que a mencionam,
nunca a súmula em si. Como são poucos, ficam indexados em memória.

O número de cada registro vem do próprio acervo. Nos dispositivos, o texto
abre com "Art. N.". Nas súmulas, quando o enunciado traz o número no
rodapé, ele é lido dali; nas demais, o enunciado é procurado dentro dos
acórdãos que o citam, e vale o número que mais vezes o antecede.
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

# Padrões para ler a citação no documento de entrada. A palavra-chave pode
# vir abreviada ("Súm. 166 do TSE") ou com ruído de digitalização
# ("5úmula 211 do STJ"); o ruído no número é tratado em normalizacao.py.
_CITACAO_SUMULA = re.compile(
    r"[S5]["
    r"úuÚU]m(?:ula)?\.?\s+(?:Vinculante\s+)?(?:n[º°.]?\s*)?(\d{1,3})",
    re.IGNORECASE,
)
# O ponto de milhar faz parte do número: "art. 1.134" é o artigo 1134. A
# digitalização às vezes entrega o separador como espaço.
_CITACAO_ARTIGO = re.compile(
    r"art(?:igo)?\.?\s*(\d{1,3}(?:[. ]\d{3})*)", re.IGNORECASE
)

_PALAVRAS_POR_JANELA = 8
_JANELAS_POR_SUMULA = 6
_CONTEXTO_ANTES = 150


def _janelas(texto: str):
    """Fatias do enunciado usadas como chave de busca, distribuídas ao
    longo do texto para não depender de onde termina o cabeçalho."""
    palavras = " ".join(texto.split()).split()
    limite = min(len(palavras) - _PALAVRAS_POR_JANELA, _JANELAS_POR_SUMULA * _PALAVRAS_POR_JANELA)
    for i in range(0, max(limite, 1), _PALAVRAS_POR_JANELA):
        yield " ".join(palavras[i : i + _PALAVRAS_POR_JANELA])


def _numero_por_citacoes(con: sqlite3.Connection, texto_sumula: str) -> str | None:
    """Número da súmula, lido do que a antecede nos acórdãos que a citam;
    vence o mais frequente."""
    votos = Counter()
    for chave in _janelas(texto_sumula):
        try:
            linhas = con.execute(
                "SELECT d.texto FROM documentos_fts JOIN documentos d"
                " ON d.rowid = documentos_fts.rowid WHERE documentos_fts MATCH ?",
                (f'"{chave}"',),
            ).fetchall()
        except sqlite3.OperationalError:
            continue  # chave com caractere não aceito pelo índice
        for (texto_doc,) in linhas:
            normalizado = " ".join(texto_doc.split())
            for ocorrencia in re.finditer(re.escape(chave), normalizado):
                inicio = max(0, ocorrencia.start() - _CONTEXTO_ANTES)
                antes = normalizado[inicio : ocorrencia.start()]
                votos.update(_NUM_SUMULA_CITADA.findall(antes))
    return votos.most_common(1)[0][0] if votos else None


# O número do artigo não identifica o dispositivo sozinho: o mesmo número
# existe em códigos diferentes. Como os textos do acervo não nomeiam o
# próprio diploma, ele é deduzido de trechos característicos do conteúdo.
_MARCAS_DE_DIPLOMA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("codigo_eleitoral", ("Tribunais Regionais são terminativas",)),
    ("codigo_penal_militar", ("ainda que gratuitamente, ter em depósito",)),
    ("cdc", ("fornecedor de serviços responde",)),
    (
        "constituicao",
        (
            "Estatuto da Magistratura",
            "direitos dos trabalhadores urbanos",
            "Todos são iguais perante a lei",
        ),
    ),
    (
        "clt",
        (
            "Recurso de Revista para Turma",
            "ônus da prova incumbe: (Redação dada",
            "extinção do contrato de trabalho",
        ),
    ),
    ("cpp", ("prisão preventiva poderá ser decretada",)),
    ("codigo_civil", ("por ação ou omissão voluntária",)),
    ("lc64", ("São inelegíveis: I - para qualquer cargo",)),
    ("cpc", ("ônus da prova incumbe: I - ao autor",)),
)

# Formas pelas quais um diploma é citado: nome por extenso, sigla ou o
# número da lei que o instituiu.
# A ordem importa: o apelido mais específico vem primeiro, para que
# "código de processo civil" não seja lido como "código civil".
_DIPLOMA_NA_CITACAO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cpc", ("código de processo civil", "cpc", "13.105", "13105")),
    ("cpp", ("código de processo penal", "cpp")),
    ("codigo_penal_militar", ("código penal militar", "cpm")),
    ("cdc", ("código de defesa do consumidor", "cdc", "8.078", "8078")),
    ("clt", ("consolidação das leis do trabalho", "clt", "13.467", "13467")),
    ("codigo_eleitoral", ("código eleitoral", "4.737", "4737")),
    ("codigo_civil", ("código civil", "10.406", "10406", " cc", "/cc")),
    ("lc64", ("lei complementar nº 64", "lei complementar 64", "lc 64", "64/1990")),
    (
        "constituicao",
        (
            "constituição",
            "cf/88",
            "cf/1988",
            "carta magna",
            "carta constitucional",
            "constituição da república",
            "constituição federal",
            " cf",
        ),
    ),
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
    """Mapa de chave para id_canonico: ("sumula", numero) e
    ("artigo", numero, diploma)."""
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
    """O trecho cita uma súmula ou um artigo de lei, exista ou não o
    registro no acervo. Uma citação normativa que não resolve é
    `inventada` e não deve seguir para a busca de acórdãos, onde o número
    casaria com qualquer documento que o mencione."""
    return bool(_CITACAO_SUMULA.search(trecho) or _CITACAO_ARTIGO.search(trecho))


def resolver_normativo(indice: dict[tuple[str, ...], int], trecho: str) -> int | None:
    """id_canonico do registro citado, ou None quando o trecho não cita
    súmula nem artigo, ou quando o registro não existe no acervo,
    inclusive se o número existir em outro diploma."""
    achado = _CITACAO_SUMULA.search(trecho)
    if achado:
        return indice.get(("sumula", achado.group(1)))
    achado = _CITACAO_ARTIGO.search(trecho)
    if achado:
        numero = re.sub(r"[. ]", "", achado.group(1))  # "1.134" -> "1134"
        diploma = _diploma_da_citacao(trecho)
        if diploma:
            return indice.get(("artigo", numero, diploma))
    return None
