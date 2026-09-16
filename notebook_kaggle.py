"""Célula única do notebook do Kaggle: gera submission.csv.

O acervo, os documentos e o código vêm do dataset anexado ao notebook. A
extração é determinística; o modelo é carregado para a única pergunta que a
estrutura não resolve, separar registros autuados com o mesmo número.
"""
import csv
import os
import sqlite3
import sys

BASE = "/kaggle/input/datasets/caiodsfelipe/desafio-bracis-projeto"
sys.path.insert(0, os.path.join(BASE, "src"))
sys.path.insert(0, BASE)

from extracao import extrair_todos
from indice_normativo import construir_indice
from llm_qwen import QwenClassificador
from resolucao import resolver_citacoes

con = sqlite3.connect(os.path.join(BASE, "desafio1_bracis.db"))
indice = construir_indice(con)
qwen = QwenClassificador()

documentos = sorted(
    f[:-4] for f in os.listdir(os.path.join(BASE, "txt")) if f.endswith(".txt")
)
linhas = []
for nome in documentos:
    caminho = os.path.join(BASE, "txt", nome + ".txt")
    texto = open(caminho, encoding="utf-8").read()
    candidatos = extrair_todos(texto)
    resolucoes = resolver_citacoes(con, qwen, indice, candidatos) if candidatos else []
    partes = [
        f"{c.inicio},{c.fim},{r.classe},"
        f"{str(r.id_canonico) if r.id_canonico else '-'},"
        f"{'-' if r.confianca is None else format(r.confianca, '.4f')}"
        for c, r in zip(candidatos, resolucoes)
    ]
    linhas.append((nome, "|".join(partes) or "-"))

with open("submission.csv", "w", newline="", encoding="utf-8") as arquivo:
    escritor = csv.writer(arquivo)
    escritor.writerow(["documento_id", "citacoes"])
    escritor.writerows(linhas)

print(f"submission.csv: {len(linhas)} documentos, {sum(l[1].count('|') + 1 for l in linhas if l[1] != '-')} citações")
