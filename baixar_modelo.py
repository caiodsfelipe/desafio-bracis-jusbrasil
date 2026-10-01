"""
Baixa os pesos do modelo para o cache do repositório.

Roda uma vez, com internet, antes da execução. A execução em si é offline:
`llm_qwen.py` carrega com `local_files_only=True` e falha com mensagem clara
se os pesos não estiverem aqui.

    python baixar_modelo.py

A revisão é fixa, de modo que o que se baixa hoje é o mesmo que se baixou
quando a solução foi medida. O destino é `modelo/`, dentro do repositório,
para que o pacote seja autocontido e não dependa do cache do usuário.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

from llm_qwen import CACHE_DO_MODELO, MODELO_ID, MODELO_REVISAO  # noqa: E402


def main() -> int:
    from huggingface_hub import snapshot_download

    print(f"baixando {MODELO_ID} @ {MODELO_REVISAO[:7]} para {CACHE_DO_MODELO}")
    CACHE_DO_MODELO.mkdir(parents=True, exist_ok=True)
    caminho = snapshot_download(
        repo_id=MODELO_ID,
        revision=MODELO_REVISAO,
        cache_dir=str(CACHE_DO_MODELO),
    )
    print(f"pronto: {caminho}")

    # Confere que o carregamento offline encontra o que acabou de chegar, para
    # que a falha apareça aqui, com internet, e não na máquina da avaliação.
    from transformers import AutoTokenizer

    AutoTokenizer.from_pretrained(
        MODELO_ID,
        revision=MODELO_REVISAO,
        cache_dir=str(CACHE_DO_MODELO),
        local_files_only=True,
    )
    print("verificado: o carregamento offline encontra os pesos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
