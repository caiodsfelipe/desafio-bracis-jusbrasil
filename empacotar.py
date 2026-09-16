"""
Monta o zip do dataset anexado ao notebook do Kaggle.

O pacote leva o código, o acervo, os documentos e os scripts da
organização, e carrega a revisão do repositório que o gerou: a verificação
de reprodutibilidade do desafio coleta o commit que produziu as saídas, e
no Kaggle não há git de onde lê-lo.

O zip é montado do zero a cada execução, e não atualizado em cima do
anterior: atualizar mantém no pacote arquivos que já saíram do repositório,
e um deles a mais é uma diferença entre o que foi medido aqui e o que roda
lá.

Uso:
    python empacotar.py
    python empacotar.py --destino outro_nome.zip
"""

import argparse
import datetime
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# O que o notebook precisa encontrar no dataset. Os scripts da organização
# vão junto para que a conversão e a métrica rodem lá com o mesmo código
# que roda aqui.
_MODULOS = "src"
_DOCUMENTOS = "txt"
_ARQUIVOS = (
    "desafio1_bracis.db",
    "goldenset_offsets.csv",
    "kaggle_metric.py",
    "json_to_submission.py",
    "sample_submission.csv",
)

_REVISAO = Path("src/revisao.py")
_MODELO_DE_REVISAO = '''"""
Revisão do código que produziu uma submissão.

A verificação de reprodutibilidade do desafio coleta o repositório e o
commit que geraram as saídas. No Kaggle não há repositório git: o que
chega é o conteúdo do dataset anexado. Por isso a revisão é gravada aqui
no momento de empacotar, por `empacotar.py`, e sai junto com o resultado.
"""

# Preenchido por empacotar.py a cada geração do zip.
COMMIT = "{commit}"
GERADO_EM = "{gerado_em}"
'''


def _revisao_do_repositorio() -> tuple[str, bool]:
    """Commit atual e se a árvore de trabalho está limpa."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        ).stdout.strip()
        pendente = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "desconhecida", False
    return commit, not pendente


def _arquivos_do_pacote() -> list[Path]:
    """Caminhos, relativos à raiz, que entram no zip."""
    caminhos = [
        caminho.relative_to(RAIZ)
        for caminho in sorted((RAIZ / _MODULOS).rglob("*.py"))
        if "__pycache__" not in caminho.parts
    ]
    caminhos += [
        caminho.relative_to(RAIZ)
        for caminho in sorted((RAIZ / _DOCUMENTOS).glob("*.txt"))
    ]
    for nome in _ARQUIVOS:
        if (RAIZ / nome).exists():
            caminhos.append(Path(nome))
    return caminhos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", default="desafio_bracis_projeto.zip")
    argumentos = parser.parse_args()

    commit, limpo = _revisao_do_repositorio()
    if not limpo:
        print(
            "aviso: há alterações não comitadas; o pacote não corresponderá"
            f" ao commit {commit[:7]}",
            file=sys.stderr,
        )
    gerado_em = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    (RAIZ / _REVISAO).write_text(
        _MODELO_DE_REVISAO.format(commit=commit, gerado_em=gerado_em),
        encoding="utf-8",
    )

    destino = RAIZ / argumentos.destino
    caminhos = _arquivos_do_pacote()
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        for relativo in caminhos:
            pacote.write(RAIZ / relativo, relativo.as_posix())

    documentos = sum(1 for c in caminhos if c.parts[0] == _DOCUMENTOS)
    modulos = sum(1 for c in caminhos if c.parts[0] == _MODULOS)
    print(f"{destino.name}: {len(caminhos)} arquivos")
    print(f"  {modulos} módulos, {documentos} documentos")
    print(f"  revisão {commit[:7]}{'' if limpo else ' (árvore suja)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
