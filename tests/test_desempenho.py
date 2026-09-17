"""
Cobertura das decisões que afetam o custo de execução.

O pipeline roda no Kaggle com tempo de GPU contado, e a passada pelo modelo
custa quase o mesmo para um prompt ou para dezesseis. O que estes casos
travam é o que torna o custo proporcional ao número de disputas, e não ao
número de documentos.
"""

import sqlite3

import pytest

from resolucao import resolver_citacoes, resolver_documentos


class _Candidato:
    def __init__(self, trecho, inicio=500):
        self.inicio = inicio
        self.fim = inicio + len(trecho)
        self.trecho = trecho
        self.origem = "padrao"


class _ModeloContado:
    """Conta as idas ao modelo, sem carregar peso algum."""

    def __init__(self):
        self.chamadas = 0
        self.prompts = 0

    def gerar_lote(self, prompt_sistema, prompts_usuario, **_):
        if prompts_usuario:
            self.chamadas += 1
            self.prompts += len(prompts_usuario)
        return [type("R", (), {"texto": "1"})() for _ in prompts_usuario]


@pytest.fixture
def acervo():
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE documentos (
            documento_id TEXT, id INTEGER, tribunal TEXT,
            natureza TEXT, texto TEXT, texto_len INTEGER
        );
        CREATE VIRTUAL TABLE documentos_fts USING fts5(
            texto, content='documentos', content_rowid='rowid',
            tokenize='unicode61'
        );
        """
    )
    return con


def test_lote_unico_faz_uma_so_ida_ao_modelo(acervo):
    """Resolver documento a documento multiplica as passadas pela GPU pelo
    número de documentos; juntar as disputas numa chamada deixa o custo
    proporcional às disputas."""
    documentos = {
        f"doc_{i}": [_Candidato("Rcl 45678/DF"), _Candidato("REsp 1.234.567/SP", 600)]
        for i in range(8)
    }
    modelo = _ModeloContado()
    resolver_documentos(acervo, modelo, {}, documentos)
    assert modelo.chamadas <= 1


def test_lote_unico_preserva_a_origem_de_cada_citacao(acervo):
    """Concatenar as citações de vários documentos não pode embaralhar a
    quem cada resolução pertence."""
    documentos = {
        "a": [_Candidato("Rcl 1111/DF")],
        "b": [],
        "c": [_Candidato("Rcl 2222/SP"), _Candidato("Rcl 3333/RJ", 700)],
    }
    resolucoes = resolver_documentos(acervo, _ModeloContado(), {}, documentos)
    assert [len(resolucoes[d]) for d in ("a", "b", "c")] == [1, 0, 2]
    assert set(resolucoes) == set(documentos)


def test_lote_unico_concorda_com_a_resolucao_por_documento(acervo):
    """A otimização não pode mudar nenhuma classificação."""
    documentos = {
        "a": [_Candidato("Rcl 45678/DF")],
        "b": [_Candidato("art. 373, I, do CPC"), _Candidato("Súmula 331 do TST", 700)],
    }
    em_lote = resolver_documentos(acervo, _ModeloContado(), {}, documentos)
    por_documento = {
        nome: resolver_citacoes(acervo, _ModeloContado(), {}, candidatos)
        for nome, candidatos in documentos.items()
    }
    for nome in documentos:
        assert [(r.classe, r.id_canonico, r.caminho) for r in em_lote[nome]] == [
            (r.classe, r.id_canonico, r.caminho) for r in por_documento[nome]
        ]


def test_modelo_nao_carrega_sem_pergunta():
    """Carregar dezesseis gigabytes para não perguntar nada custa metade do
    tempo de execução; a saída vazia precede qualquer toque nos pesos."""
    from llm_qwen import QwenClassificador

    qwen = QwenClassificador()
    assert qwen.gerar_lote("sistema", []) == []
    assert not qwen.carregado
