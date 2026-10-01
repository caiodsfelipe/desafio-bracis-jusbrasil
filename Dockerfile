# Ambiente da execução do Desafio Caça-Alucinações.
#
# A imagem base traz CUDA 12.1 e Python 3.11, e o torch fixado em
# requirements.txt é a build cu121 correspondente. Python 3.11 por ser a
# versão para a qual existe roda de torch estável; o código exige 3.10+.
#
#   docker build -t caca-alucinacoes .
#
#   # uma vez, com internet, para trazer os pesos:
#   docker run --rm --gpus all -v "$PWD/modelo:/app/modelo" \
#       caca-alucinacoes python baixar_modelo.py
#
#   # execução, offline:
#   docker run --rm --gpus all --network none \
#       -v "$PWD/modelo:/app/modelo" -v "$PWD/dados:/dados" \
#       caca-alucinacoes bash run.sh /dados/acervo.db /dados/txt /dados/submission.csv
#
# Os pesos ficam num volume, e não dentro da imagem, para que a imagem seja
# leve e os 16 GB sejam baixados uma única vez.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

# Sem bytecode e sem buffer: a saída aparece no log na ordem em que acontece.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app

# As dependências vêm antes do código, para que uma mudança no código não
# invalide a camada de instalação.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY tests/ tests/
COPY executar.py baixar_modelo.py run.sh pyproject.toml ./
COPY kaggle_metric.py json_to_submission.py ./

# `baixar_modelo.py` precisa de rede, e por isso roda num `docker run`
# próprio, não aqui: a construção da imagem não baixa os pesos.
RUN chmod +x run.sh

# A suíte de regressão não toca banco nem modelo, e roda em milissegundos:
# falhar aqui denuncia um ambiente diferente do que foi medido.
RUN python -m pytest tests/ -q

ENTRYPOINT []
CMD ["bash", "run.sh"]
