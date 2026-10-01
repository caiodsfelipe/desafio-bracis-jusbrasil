# Caça-Alucinações

Verifica citações jurídicas em pareceres gerados por IA. Dado um documento,
localiza cada citação de jurisprudência ou de lei e a classifica como `real`
(com o `id_canonico` do registro no acervo), `inventada` ou `incompleta`.

Solução para o Desafio 1 do BRACIS 2026 × Jusbrasil. Marca **1.100** no
conjunto de desenvolvimento, o teto da métrica oficial.

Cada citação percorre quatro etapas:

1. **Extração** por padrões, em duas frentes: as citações que trazem
   identificador (processo, súmula, tema, artigo) e as que descrevem o julgado
   por tribunal, ano e relator. As duas são mescladas por IoU ≥ 0,5.
2. **Normalização** do identificador dentro do span, que desfaz o ruído de
   digitalização (`0↔O`, `1↔l`, `5↔S`) e remonta o número quebrado por espaço
   ou quebra de linha.
3. **Resolução** contra o acervo: súmulas e artigos pelo índice normativo,
   chaveado por número e diploma; acórdãos por busca exata no FTS5, em que a
   posição do número no documento encontrado distingue o processo citado de
   quem apenas o menciona.
4. **Classificação**, com a confiança declarada pelo caminho que resolveu a
   citação.

O modelo entra em um só ponto: quando dois processos foram autuados com o
mesmo número e diferem apenas na espécie do recurso, caso em que só a leitura
dos cabeçalhos os separa. No conjunto de desenvolvimento isso ocorre uma vez
em 192 citações.

Construído com [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) e SQLite FTS5.

## Executar

Baixe os pesos uma vez, com internet:

```bash
python baixar_modelo.py          # Qwen3-8B em revisão fixa, para ./modelo (16 GB)
```

Depois a execução é offline:

```bash
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
```

Grava o CSV no formato das submissões e, ao lado dele, os JSONs do contrato.
Os três caminhos chegam por argumento.

Em bfloat16 o modelo ocupa cerca de 16,4 GB e cabe numa placa de 24 GB.
`device_map="auto"` usa a placa única quando há uma e reparte quando há mais.
A decodificação é gulosa e `run.sh` fixa `PYTHONHASHSEED`, de modo que a mesma
entrada produz sempre a mesma saída.

## Docker

```bash
docker build -t caca-alucinacoes .

# uma vez, com internet, para trazer os pesos ao volume:
docker run --rm --gpus all -v "$PWD/modelo:/app/modelo" \
    caca-alucinacoes python baixar_modelo.py

# execução, sem rede:
docker run --rm --gpus all --network none \
    -v "$PWD/modelo:/app/modelo" -v "$PWD/dados:/dados" \
    caca-alucinacoes bash run.sh /dados/acervo.db /dados/txt /dados/submission.csv
```

A construção da imagem roda a suíte de testes. As versões estão fixas em
`requirements.txt`.

## Desenvolvimento

Os dados da competição não são redistribuídos aqui. Baixe
`desafio1_bracis.db`, `txt/`, o `goldenset` e `kaggle_metric.py` da aba *Data*
da competição e coloque na raiz do projeto.

```bash
pip install -r requirements.txt

pytest tests/                    # testes offline: sem banco, sem modelo
ruff check src tests
python avaliar.py                # score contra o conjunto de referência
python avaliar.py --com-modelo   # pipeline completo, requer GPU
```

`avaliar.py` imprime o score por nível, a cobertura da extração e o acerto por
caminho de resolução, marcando com `*` os que dependem do modelo.
`--json relatorio.json` grava o relatório completo.

CI (`.github/workflows/testes.yml`) roda os testes e o linter em cada push.

## Generalização

O conjunto final são documentos que ninguém viu. Estas ferramentas medem o
comportamento fora da amostra distribuída:

```bash
python robustez.py               # score sob perturbação dos documentos
python generalizacao.py          # desempenho documento a documento
python corpus.py                 # forma dos trechos nos acórdãos do acervo
python contraprova.py <base>     # score contra outra versão do conjunto
python ablacao.py --base-antiga <base>
python comparar.py <revisão>     # diferença de comportamento entre revisões
```

- **Duas versões do dataset.** 1,0819 na anterior e 1,1000 na final.
- **Ablação.** Desativando cada regra, a assimetria entre as duas bases é no
  máximo 0,0037 contra uma queda de até 0,42.
- **Robustez.** Sob ruído de digitalização em 2% dos algarismos o score é
  1,0880; com o ponto de milhar entregue como espaço, 1,0746.
- **Por documento.** Nenhum documento cai mais de 0,01 abaixo da referência.
- **Acórdãos reais.** Os 1014 acórdãos do acervo são peças reais de cinco
  tribunais, e `corpus.py` audita os padrões contra eles. Sobre 40 deles como
  entrada, o pipeline rende 7.599 citações sem exceções.
- **Testes metamórficos.** A mesma citação em sete formulações recebe a mesma
  classe e o mesmo `id_canonico`; a ordem das citações não altera nenhuma.

## Estrutura

```
src/
  regex_extracao.py       citações com identificador
  regex_prosa.py          citações sem identificador
  especie_recurso.py      família do recurso, que separa feitos de mesmo número
  extracao.py             mescla as fontes e deduplica por IoU
  normalizacao.py         normaliza o identificador dentro do span
  indice_normativo.py     índice das súmulas e dos dispositivos
  resolucao.py            busca no acervo, roteamento, classe e confiança
  contrato.py             saída no formato do desafio
  llm_qwen.py             carregamento e geração
  prompts/                prompts versionados
run.sh, executar.py       ponto de entrada
baixar_modelo.py          baixa os pesos em revisão fixa
avaliar.py                avaliação contra o conjunto de referência
robustez.py, generalizacao.py, contraprova.py, ablacao.py, corpus.py, comparar.py
notebook_kaggle.py, empacotar.py   artefatos do Kaggle
tests/                    testes offline
```

O artefato oficial é um JSON por documento, de onde o `submission.csv` sai
pelo conversor da organização; um teste trava que o CSV escrito direto é byte
a byte o que o conversor produziria.

## Licença

[MIT](LICENSE). Os dados da competição pertencem à organização do desafio.
