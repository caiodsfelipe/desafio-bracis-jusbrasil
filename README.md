# Caça-Alucinações

Verifica citações jurídicas em pareceres gerados por IA. Dado um documento,
localiza cada citação de jurisprudência ou de lei e a classifica como `real`
(com o `id_canonico` do registro no acervo), `inventada` ou `incompleta`.

Um modelo de linguagem que inventa um número de processo produz uma citação
com a forma exata de uma verdadeira: a sigla do recurso, o número com
separador de milhar, a sigla da UF, o relator. A diferença não está no texto,
e sim em haver ou não um processo com aquele número. Um número quase idêntico
ao de um processo real aponta um processo diferente, não o mesmo.

Solução para o Desafio 1 do BRACIS 2026 × Jusbrasil, onde marcou **1.100**, o
teto da métrica oficial: macro-F1 de 1,0 nos dois níveis e nenhum erro grave.

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

A entrada é um SQLite com o acervo de jurisprudência, que reúne os acórdãos,
as súmulas e os dispositivos de lei contra os quais cada citação é verificada,
e uma pasta de documentos em `.txt`.

```bash
python baixar_modelo.py                                  # pesos, uma vez
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
```

Grava um CSV com o span, a classe, o `id_canonico` e a confiança de cada
citação, e os JSONs equivalentes ao lado dele.

Em bfloat16 o modelo ocupa cerca de 16,4 GB e cabe numa placa de 24 GB;
`device_map="auto"` usa a placa única quando há uma e reparte quando há mais.
A decodificação é gulosa e `run.sh` fixa `PYTHONHASHSEED`: a mesma entrada
produz sempre a mesma saída. Depois do download inicial nada depende da rede,
e `MODELO_ONLINE=1` com `CACHE_DO_MODELO` reaponta os pesos para ambientes de
sistema de arquivos somente leitura, como o notebook do Kaggle.

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

```bash
pip install -r requirements.txt
pytest tests/                    # 281 testes, em milissegundos
ruff check src tests
```

A suíte roda sem banco, sem modelo e sem rede: os padrões de extração, a
normalização e as regras de classificação são exercitados sobre casos
literais, e é o que torna o ciclo de desenvolvimento rápido. Os testes que
precisam dos dados da competição pulam quando eles não estão presentes.

Os dados pertencem à organização do desafio e não são redistribuídos aqui.
Com eles na raiz do projeto (`desafio1_bracis.db`, `txt/`, o `goldenset` e
`kaggle_metric.py`), a avaliação reproduz o score:

```bash
python avaliar.py                # score contra o conjunto de referência
python avaliar.py --com-modelo   # pipeline completo, requer GPU
```

`avaliar.py` imprime o score por nível, a cobertura da extração e o acerto por
caminho de resolução, marcando com `*` os que dependem do modelo.

CI (`.github/workflows/testes.yml`) roda os testes e o linter em cada push.

## Generalização

Um score alto em vinte e seis documentos não distingue a regra que capturou o
critério da que se ajustou à amostra. Estas ferramentas medem o comportamento
fora dela:

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

A saída canônica é um JSON por documento, e o CSV deriva dele; um teste trava
que as duas formas descrevem a mesma predição, byte a byte.

## Licença

[MIT](LICENSE). Os dados da competição pertencem à organização do desafio.
