#!/usr/bin/env bash
#
# Ponto de entrada único da solução.
#
#   bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
#
# Exemplo:
#   bash run.sh desafio1_bracis.db txt/ submission.csv
#
# A execução é offline e determinística. Os pesos do modelo precisam já estar
# em `modelo/`, baixados por `python baixar_modelo.py` antes da execução.
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "uso: bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>" >&2
    exit 2
fi

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Nenhuma chamada à rede durante a execução: os pesos vêm do cache local, e
# exigir o modo offline faz um acesso acidental falhar em vez de pendurar.
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Determinismo entre execuções, como as regras de envio recomendam. A
# decodificação já é gulosa; isto cobre a inicialização das bibliotecas.
export PYTHONHASHSEED=0
export CUBLAS_WORKSPACE_CONFIG=:4096:8

exec python "$RAIZ/executar.py" "$1" "$2" "$3"
