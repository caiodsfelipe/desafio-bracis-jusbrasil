"""Célula única do notebook do Kaggle: gera os JSONs do contrato e o
submission.csv.

O acervo, os documentos e o código vêm do dataset anexado ao notebook. A
extração é determinística; o modelo é carregado para a única pergunta que a
estrutura não resolve, separar registros autuados com o mesmo número.

O artefato oficial da solução é o JSON por documento, de onde o CSV sai
pelo conversor da organização. Os dois são gravados aqui, e o CSV escrito
direto é byte a byte o que `json_to_submission.py` produziria a partir dos
JSONs: a verificação de reprodutibilidade encontra o formato que confere.
"""
import csv
import os
import pathlib
import sqlite3
import sys

BASE = "/kaggle/input/datasets/caiodsfelipe/desafio-bracis-projeto"
sys.path.insert(0, os.path.join(BASE, "src"))
sys.path.insert(0, BASE)

import revisao
from contrato import gravar
from extracao import extrair_todos
from indice_normativo import construir_indice
from llm_qwen import QwenClassificador
from resolucao import resolver_citacoes

print(f"revisão {revisao.COMMIT}, empacotada em {revisao.GERADO_EM}")

con = sqlite3.connect(os.path.join(BASE, "desafio1_bracis.db"))
indice = construir_indice(con)
qwen = QwenClassificador()

documentos = sorted(
    f[:-4] for f in os.listdir(os.path.join(BASE, "txt")) if f.endswith(".txt")
)
saida_json = pathlib.Path("jsons")
linhas = []
for nome in documentos:
    caminho = os.path.join(BASE, "txt", nome + ".txt")
    texto = open(caminho, encoding="utf-8").read()
    candidatos = extrair_todos(texto)
    resolucoes = resolver_citacoes(con, qwen, indice, candidatos) if candidatos else []
    gravar(saida_json, nome, candidatos, resolucoes)
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

citacoes = sum(linha[1].count("|") + 1 for linha in linhas if linha[1] != "-")
print(f"{saida_json}/: {len(documentos)} JSONs do contrato")
print(f"submission.csv: {len(linhas)} documentos, {citacoes} citações")
