# -*- coding: utf-8 -*-
"""
Pipeline de ponta a ponta SEM LLM (só regex + normalização + busca no
banco), para achar bugs de integração antes de gastar cota de GPU no
Kaggle testando as partes que dependem do Qwen3-8B.

Etapa "dono vs citação" fica DESLIGADA aqui (aceita todo candidato como
dono) — sem isso, o pipeline não decide isso sozinho ainda (depende do
LLM, ver resolucao.py). Resultado esperado: superestimar "incompleta"
sempre que houver 2+ candidatos no banco para um identificador, mesmo
quando só 1 seria o dono de fato.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from regex_extracao import extrair_candidatos
from normalizacao import normalizar_identificadores
from resolucao import buscar_candidatos, decidir_classe


def processar_documento(con: sqlite3.Connection, texto: str) -> list[tuple[int, int, str, str, int | None]]:
    """Retorna [(inicio, fim, trecho, classe, id_canonico), ...] para cada
    citação encontrada pelo regex (LLM de prosa livre ainda não incluído
    neste teste)."""
    resultados = []
    for inicio, fim, trecho in extrair_candidatos(texto):
        idents = normalizar_identificadores(trecho)
        todos_candidatos = []
        for ident in idents:
            todos_candidatos.extend(buscar_candidatos(con, ident))
        # SEM filtro de dono/citação — aceita todos (ver docstring do módulo)
        classe, id_canonico = decidir_classe(todos_candidatos)
        resultados.append((inicio, fim, trecho, classe, id_canonico))
    return resultados


if __name__ == "__main__":
    projeto = Path(__file__).parent.parent
    con = sqlite3.connect(projeto / "desafio1_bracis.db")

    txt_dir = projeto / "txt"
    for arquivo in sorted(txt_dir.glob("*.txt"))[:2]:
        texto = arquivo.read_text(encoding="utf-8")
        print(f"=== {arquivo.stem} ===")
        for inicio, fim, trecho, classe, id_canonico in processar_documento(con, texto):
            print(f"  [{inicio},{fim}) {classe:12} {id_canonico or '-':12} {trecho[:50]!r}")
