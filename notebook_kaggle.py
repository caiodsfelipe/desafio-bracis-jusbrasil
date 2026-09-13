import csv, os, sqlite3, sys

RAIZ = "/kaggle/input/desafio-bracis-projeto"
sys.path.insert(0, os.path.join(RAIZ, "src"))
sys.path.insert(0, RAIZ)

from extracao import extrair_todos
from indice_normativo import construir_indice
from llm_qwen import QwenClassificador
from resolucao import resolver_citacoes

con = sqlite3.connect(os.path.join(RAIZ, "desafio1_bracis.db"))
indice = construir_indice(con)
qwen = QwenClassificador()

documentos = sorted(
    f[:-4] for f in os.listdir(os.path.join(RAIZ, "txt")) if f.endswith(".txt")
)
linhas = []
for nome in documentos:
    caminho = os.path.join(RAIZ, "txt", nome + ".txt")
    texto = open(caminho, encoding="utf-8").read()
    candidatos = extrair_todos(texto)
    resolucoes = resolver_citacoes(con, qwen, indice, candidatos) if candidatos else []
    partes = [
        f"{c.inicio},{c.fim},{r.classe},"
        f"{str(r.id_canonico) if r.id_canonico else '-'},{r.confianca:.4f}"
        for c, r in zip(candidatos, resolucoes)
    ]
    linhas.append((nome, "|".join(partes) or "-"))

with open("submission.csv", "w", newline="", encoding="utf-8") as arquivo:
    escritor = csv.writer(arquivo)
    escritor.writerow(["documento_id", "citacoes"])
    escritor.writerows(linhas)

print(f"submission.csv: {len(linhas)} documentos, {sum(l[1].count('|') + 1 for l in linhas if l[1] != '-')} citações")
