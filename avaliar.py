"""
Avaliação do pipeline contra o conjunto de referência.

Reproduz a métrica oficial e detalha o resultado por caminho de resolução,
que é o que indica onde uma mudança ajudou ou atrapalhou. O relatório traz
a versão de cada prompt e o commit, para que um número possa sempre ser
reproduzido.

Uso:
    python avaliar.py                 avaliação determinística, sem modelo
    python avaliar.py --com-modelo    carrega o Qwen3-8B e usa o pipeline completo
    python avaliar.py --json saida.json

A extração é determinística. O modelo só é consultado para separar
registros do acervo autuados com o mesmo número, e sem ele essas perguntas
recebem a primeira opção como resposta; o relatório informa quantas foram.
"""
import argparse
import collections
import csv
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

CAMINHOS_DETERMINISTICOS = (
    "normativo",
    "sem_identificador",
    "registro_unico",
    "cabecalho",
    "sem_candidato",
    "so_mencionado",
)


class ModeloAusente:
    """Responde sempre a primeira opção, sem carregar pesos."""

    def __init__(self):
        self.chamadas = 0

    def gerar_lote(self, prompt_sistema, prompts_usuario, **_):
        from llm_qwen import RespostaLLM

        self.chamadas += len(prompts_usuario)
        return [RespostaLLM("1") for _ in prompts_usuario]

    def gerar(self, prompt_sistema, prompt_usuario, **kwargs):
        return self.gerar_lote(prompt_sistema, [prompt_usuario], **kwargs)[0]


def carregar_gabarito(caminho):
    """Gabarito por documento. O arquivo distribuído vem com marca de ordem
    de bytes, que `utf-8-sig` descarta para que a primeira coluna tenha o
    nome esperado."""
    por_documento = collections.defaultdict(list)
    with open(caminho, encoding="utf-8-sig") as arquivo:
        for linha in csv.DictReader(arquivo):
            por_documento[linha["documento_id"]].append(linha)
    return por_documento


def _celula_do_gabarito(citacoes):
    partes = []
    for c in citacoes:
        doc_ids = str(int(float(c["id_canonico"]))) if c["id_canonico"] else "-"
        partes.append(f"{c['inicio']},{c['fim']},{c['classificacao']},{doc_ids}")
    return "|".join(partes) or "-"


def _celula_da_predicao(candidatos, resolucoes):
    partes = []
    for candidato, resolucao in zip(candidatos, resolucoes, strict=True):
        id_canonico = str(resolucao.id_canonico) if resolucao.id_canonico else "-"
        # A confiança é opcional, e o caminho que não a declara fica fora da
        # média do Brier em vez de puxá-la para baixo.
        confianca = (
            "-" if resolucao.confianca is None else f"{resolucao.confianca:.4f}"
        )
        partes.append(
            f"{candidato.inicio},{candidato.fim},{resolucao.classe},"
            f"{id_canonico},{confianca}"
        )
    return "|".join(partes) or "-"


def prever(con, modelo, indice, texto):
    """Candidatos e resoluções de um documento."""
    from extracao import extrair_todos
    from resolucao import resolver_citacoes

    candidatos = extrair_todos(texto)
    if not candidatos:
        return [], []
    return candidatos, resolver_citacoes(con, modelo, indice, candidatos)


def _iou(a, b):
    intersecao = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    if not intersecao:
        return 0.0
    return intersecao / ((a[1] - a[0]) + (b[1] - b[0]) - intersecao)


def acertos_por_caminho(gabarito, predicoes):
    """Acertos e total de cada caminho de resolução, casando predição e
    gabarito pelo mesmo critério da métrica oficial."""
    contagem = collections.defaultdict(lambda: [0, 0])
    for documento, (candidatos, resolucoes) in predicoes.items():
        for candidato, resolucao in zip(candidatos, resolucoes, strict=True):
            esperado = None
            span = (candidato.inicio, candidato.fim)
            for c in gabarito[documento]:
                if _iou((int(c["inicio"]), int(c["fim"])), span) >= 0.5:
                    esperado = (
                        c["classificacao"],
                        int(float(c["id_canonico"])) if c["id_canonico"] else None,
                    )
                    break
            registro = contagem[resolucao.caminho]
            registro[0] += esperado == (resolucao.classe, resolucao.id_canonico)
            registro[1] += 1
    return {k: tuple(v) for k, v in sorted(contagem.items())}


def citacoes_nao_extraidas(gabarito, predicoes):
    faltantes = []
    for documento, citacoes in gabarito.items():
        candidatos, _ = predicoes[documento]
        for c in citacoes:
            alvo = (int(c["inicio"]), int(c["fim"]))
            if not any(_iou(alvo, (x.inicio, x.fim)) >= 0.5 for x in candidatos):
                faltantes.append(f"{documento}:{c['citacao_id']}")
    return faltantes


def versao_do_codigo():
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "desconhecida"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acervo", default=str(RAIZ / "desafio1_bracis.db"))
    parser.add_argument("--gabarito", default=str(RAIZ / "goldenset_offsets.csv"))
    parser.add_argument("--documentos", default=str(RAIZ / "txt"))
    parser.add_argument("--com-modelo", action="store_true")
    parser.add_argument("--json", help="grava o relatório completo neste arquivo")
    argumentos = parser.parse_args()

    import sqlite3

    import kaggle_metric
    import pandas as pd

    from indice_normativo import construir_indice
    from prompts.escolha_de_registro import VIGENTE as PROMPT_ESCOLHA

    con = sqlite3.connect(argumentos.acervo)
    indice = construir_indice(con)
    gabarito = carregar_gabarito(argumentos.gabarito)

    if argumentos.com_modelo:
        from llm_qwen import QwenClassificador

        modelo = QwenClassificador()
    else:
        modelo = ModeloAusente()

    solucao, submissao, predicoes = [], [], {}
    for documento in sorted(gabarito):
        texto = Path(argumentos.documentos, f"{documento}.txt").read_text(encoding="utf-8")
        candidatos, resolucoes = prever(con, modelo, indice, texto)
        predicoes[documento] = (candidatos, resolucoes)
        solucao.append(
            {
                "documento_id": documento,
                "nivel": int(gabarito[documento][0]["nivel"]),
                "Usage": "Public",
                "citacoes": _celula_do_gabarito(gabarito[documento]),
            }
        )
        submissao.append(
            {
                "documento_id": documento,
                "citacoes": _celula_da_predicao(candidatos, resolucoes),
            }
        )

    resultado = kaggle_metric.avaliar(
        pd.DataFrame(solucao), pd.DataFrame(submissao), "documento_id"
    )
    faltantes = citacoes_nao_extraidas(gabarito, predicoes)
    caminhos = acertos_por_caminho(gabarito, predicoes)
    total_citacoes = sum(len(v) for v in gabarito.values())

    relatorio = {
        "commit": versao_do_codigo(),
        "prompts": {PROMPT_ESCOLHA.nome: PROMPT_ESCOLHA.versao},
        "modelo": "Qwen/Qwen3-8B" if argumentos.com_modelo else "ausente",
        "consultas_ao_modelo": getattr(modelo, "chamadas", None),
        "score_final": resultado["score_final"],
        "niveis": {
            str(nivel): {
                "score": dados["score"],
                "macro_f1": dados["macro_f1"],
                "f1_por_classe": dados["f1_por_classe"],
                "erro_grave": dados["tau"],
                "bonus_calibracao": dados["b"],
            }
            for nivel, dados in resultado["niveis"].items()
        },
        "extracao": {
            "citacoes_do_gabarito": total_citacoes,
            "nao_extraidas": len(faltantes),
            "quais": faltantes,
        },
        "caminhos": {k: {"acertos": a, "total": n} for k, (a, n) in caminhos.items()},
    }

    print(f"score final      {relatorio['score_final']:.6f}")
    for nivel, dados in relatorio["niveis"].items():
        print(
            f"  nivel {nivel}        {dados['score']:.4f}"
            f"  macro-F1 {dados['macro_f1']:.4f}"
            f"  erro grave {dados['erro_grave']:.4f}"
        )
    print(f"extracao         {total_citacoes - len(faltantes)}/{total_citacoes}")
    print("caminhos")
    for caminho, (acertos, total) in caminhos.items():
        marca = " " if caminho in CAMINHOS_DETERMINISTICOS else "*"
        print(f"  {marca}{caminho:<20}{acertos:>4}/{total:<4} {acertos / total:.3f}")
    print("* depende do modelo")

    if argumentos.json:
        Path(argumentos.json).write_text(
            json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nrelatorio em {argumentos.json}")


if __name__ == "__main__":
    main()
