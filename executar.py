"""
Ponto de entrada único da solução.

Recebe o caminho do acervo, a pasta com os documentos e o arquivo de saída,
e grava o `submission.csv` no formato das submissões. É o que a organização
executa sobre o conjunto final, numa máquina limpa e sem internet.

    python executar.py <caminho_db> <pasta_txt> <arquivo_saida>

Nada aqui depende de caminho absoluto, de variável de ambiente ou de
arquivo que exista apenas na máquina de desenvolvimento: os três caminhos
chegam por argumento, e o resto vem do próprio repositório.

Os JSONs do contrato são gravados ao lado da saída, num diretório irmão, por
serem o artefato oficial da solução; o CSV sai deles pelo mesmo formato que
`json_to_submission.py` produz.
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))


def _documentos(pasta: Path) -> list[str]:
    """Identificadores dos documentos de entrada, em ordem estável."""
    return sorted(caminho.stem for caminho in pasta.glob("*.txt"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica as citações jurídicas dos documentos de entrada."
    )
    parser.add_argument("acervo", type=Path, help="caminho do .db do acervo")
    parser.add_argument("documentos", type=Path, help="pasta com os .txt")
    parser.add_argument("saida", type=Path, help="arquivo .csv a gravar")
    parser.add_argument(
        "--jsons",
        type=Path,
        default=None,
        help="pasta dos JSONs do contrato (padrão: 'jsons' ao lado da saída)",
    )
    argumentos = parser.parse_args()

    for caminho in (argumentos.acervo, argumentos.documentos):
        if not caminho.exists():
            parser.error(f"caminho inexistente: {caminho}")

    from contrato import celula_da_predicao, gravar
    from extracao import extrair_todos
    from indice_normativo import construir_indice
    from llm_qwen import QwenClassificador
    from resolucao import resolver_documentos

    con = sqlite3.connect(argumentos.acervo)
    indice = construir_indice(con)
    qwen = QwenClassificador()

    documentos = _documentos(argumentos.documentos)
    if not documentos:
        parser.error(f"nenhum .txt em {argumentos.documentos}")

    # A extração percorre todos os documentos antes de qualquer resolução,
    # para que as disputas de todos eles caibam numa só ida ao modelo.
    candidatos_por_documento = {
        nome: extrair_todos(
            (argumentos.documentos / f"{nome}.txt").read_text(encoding="utf-8")
        )
        for nome in documentos
    }
    resolucoes_por_documento = resolver_documentos(
        con, qwen, indice, candidatos_por_documento
    )

    saida_json = argumentos.jsons or argumentos.saida.resolve().parent / "jsons"
    linhas = []
    for nome in documentos:
        candidatos = candidatos_por_documento[nome]
        resolucoes = resolucoes_por_documento[nome]
        gravar(saida_json, nome, candidatos, resolucoes)
        linhas.append((nome, celula_da_predicao(candidatos, resolucoes)))

    argumentos.saida.resolve().parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["documento_id", "citacoes"])
        escritor.writerows(linhas)

    citacoes = sum(linha[1].count("|") + 1 for linha in linhas if linha[1] != "-")
    print(f"{saida_json}/: {len(documentos)} JSONs do contrato")
    print(f"{argumentos.saida}: {len(linhas)} documentos, {citacoes} citações")
    print(
        "modelo carregado"
        if qwen.carregado
        else "modelo não foi necessário: a estrutura resolveu todas as citações"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
