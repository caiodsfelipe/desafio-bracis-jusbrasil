"""
Comparação do pipeline com uma versão anterior do próprio repositório.

A avaliação local substitui o modelo por uma resposta fixa, e por isso não
enxerga o que muda no caminho do LLM: um prompt reescrito produz outra
saída na avaliação oficial sem alterar nada aqui. Esta ferramenta fecha
essa lacuna comparando duas coisas entre a versão de referência e a de
trabalho:

    as predições de cada documento, e
    os prompts que seriam enviados ao modelo, palavra por palavra.

Uma diferença em qualquer das duas muda o resultado da submissão. Rode
antes de submeter, contra a revisão do melhor resultado conhecido.

Uso:
    python comparar.py v1.0.0
    python comparar.py a6bf2a3 --documentos txt
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


class ModeloEspiao:
    """Registra cada prompt e devolve sempre a mesma resposta, para que a
    diferença observada venha do pipeline e não do modelo."""

    def __init__(self):
        self.prompts = []

    def gerar_lote(self, prompt_sistema, prompts_usuario, **_):
        from llm_qwen import RespostaLLM

        self.prompts.extend((prompt_sistema, u) for u in prompts_usuario)
        return [RespostaLLM("1") for _ in prompts_usuario]

    def gerar(self, prompt_sistema, prompt_usuario, **_):
        from llm_qwen import RespostaLLM

        self.prompts.append((prompt_sistema, prompt_usuario))
        return RespostaLLM("[]")


def executar(fonte: Path, acervo: str, documentos: str) -> dict:
    """Predições e prompts de uma versão do código, num processo à parte
    para que os módulos de uma não contaminem os da outra."""
    programa = f"""
import json, os, sqlite3, sys
sys.path.insert(0, {str(fonte)!r})
sys.path.insert(0, {str(RAIZ)!r})
from comparar import ModeloEspiao
from extracao import extrair_todos
from indice_normativo import construir_indice
from resolucao import resolver_citacoes

# A versão comparada pode ter uma etapa de extração pelo modelo que a outra
# não tem. Cada uma roda o próprio pipeline, para que a diferença apareça.
try:
    from prompt_extracao import extrair_citacoes
except ImportError:
    extrair_citacoes = None

con = sqlite3.connect({acervo!r})
indice = construir_indice(con)
predicoes = {{}}
espiao = ModeloEspiao()
for nome in sorted(f[:-4] for f in os.listdir({documentos!r}) if f.endswith(".txt")):
    texto = open(os.path.join({documentos!r}, nome + ".txt"), encoding="utf-8").read()
    if extrair_citacoes is None:
        candidatos = extrair_todos(texto)
    else:
        candidatos = extrair_todos(texto, extrair_citacoes(espiao, texto))
    resolucoes = resolver_citacoes(con, espiao, indice, candidatos) if candidatos else []
    predicoes[nome] = [
        [c.inicio, c.fim, r.classe, r.id_canonico, round(r.confianca, 4)]
        for c, r in zip(candidatos, resolucoes)
    ]
print(json.dumps({{"predicoes": predicoes, "prompts": espiao.prompts}}, ensure_ascii=False))
"""
    saida = subprocess.run(
        [sys.executable, "-c", programa], capture_output=True, text=True, check=True
    )
    return json.loads(saida.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("referencia", help="revisão ou tag a comparar (ex.: v1.0.0)")
    parser.add_argument("--acervo", default=str(RAIZ / "desafio1_bracis.db"))
    parser.add_argument("--documentos", default=str(RAIZ / "txt"))
    argumentos = parser.parse_args()

    with tempfile.TemporaryDirectory() as temporario:
        with open(f"{temporario}/src.tar", "wb") as pacote:
            subprocess.run(
                ["git", "archive", argumentos.referencia, "src"],
                cwd=RAIZ, check=True, stdout=pacote,
            )
        shutil.unpack_archive(f"{temporario}/src.tar", temporario, "tar")
        antes = executar(Path(temporario) / "src", argumentos.acervo, argumentos.documentos)
    agora = executar(RAIZ / "src", argumentos.acervo, argumentos.documentos)

    divergentes = [
        nome
        for nome in antes["predicoes"]
        if antes["predicoes"][nome] != agora["predicoes"].get(nome)
    ]
    prompts_iguais = antes["prompts"] == agora["prompts"]

    print(f"referência       {argumentos.referencia}")
    print(f"documentos       {len(antes['predicoes'])}")
    print(f"predições        {'iguais' if not divergentes else f'{len(divergentes)} divergem'}")
    for nome in divergentes[:10]:
        print(f"    {nome}")
    print(
        f"prompts ao LLM   {len(antes['prompts'])} antes, "
        f"{len(agora['prompts'])} agora, "
        f"{'iguais' if prompts_iguais else 'DIFERENTES'}"
    )
    if not prompts_iguais:
        for antigo, novo in zip(antes["prompts"], agora["prompts"], strict=False):
            if antigo != novo:
                print(f"    primeiro sistema divergente:\n      antes {antigo[0][:120]!r}")
                print(f"      agora {novo[0][:120]!r}")
                break

    if divergentes or not prompts_iguais:
        print("\nO resultado da submissão vai mudar.")
        return 1
    print("\nComportamento idêntico: a submissão reproduz o resultado da referência.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
