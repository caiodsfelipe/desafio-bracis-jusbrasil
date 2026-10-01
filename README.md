# Caça-Alucinações · BRACIS 2026 × Jusbrasil

Verificação de citações jurídicas em pareceres gerados por IA. Dado um
documento, localizar cada citação de jurisprudência ou de lei e classificá-la
como `real` (com o `id_canonico` do registro), `inventada` ou `incompleta`.

No conjunto de desenvolvimento a solução alcança **1.100**, o teto da métrica
oficial: macro-F1 de 1,0 nos dois níveis, nenhum erro grave e as 192 citações
extraídas.

## Abordagem

Pipeline *retrieve-then-verify*, não RAG semântico. Citações jurídicas são
identificadores formais, e quem decide se um processo existe é uma busca exata
no acervo, não similaridade de embedding: dois números de processo quase
idênticos são documentos diferentes, e é aí que a métrica pune mais, porque
confundir `inventada` com `real` custa metade da nota do nível.

```
texto do documento
        │
        ├── padrões estruturais (identificador: processo, súmula, tema, artigo)
        └── padrões de prosa    (tribunal + ano + relator, sem número)
                    │
                    └──► mesclagem por IoU >= 0.5 ──► candidatos
                                                          │
              ┌───────────────────────────────────────────┤
      súmula ou artigo?                             acórdão?
              │                                           │
      índice normativo                     busca exata no FTS5 pelo
      (18 registros, por                   identificador normalizado
       número e diploma)                              │
              │                          posição do número no candidato
              │                                       │
              │                    ┌──────────────────┼──────────────────┐
              │              no cabeçalho        em nenhum        em vários
              │              de um só           cabeçalho         cabeçalhos
              │                  │                  │                  │
              │                real              inventada        LLM escolhe
              │                                                    pela espécie
              └──────────────────────────────────────────────────► classe + confiança
```

## Estrutura

```
src/
  regex_extracao.py        citações com identificador (processo, súmula, tema, artigo)
  regex_prosa.py           citações sem identificador (órgão, ano, relator)
  especie_recurso.py       família do recurso, que separa feitos de mesmo número
  extracao.py              mescla as fontes e deduplica por IoU
  normalizacao.py          normaliza o identificador dentro do span
  indice_normativo.py      índice dos 18 registros de súmula e dispositivo
  resolucao.py             busca no acervo, roteamento, classe e confiança
  contrato.py              saída no formato do contrato do desafio
  llm_qwen.py              carregamento e geração com o Qwen3-8B
  prompts/                 prompts versionados
tests/                     suíte de regressão, sem banco e sem modelo
run.sh                     ponto de entrada único: <db> <pasta_txt> <saida>
executar.py                pipeline completo, com os caminhos por argumento
baixar_modelo.py           traz os pesos na revisão fixa, para rodar offline
Dockerfile                 ambiente declarado, com as versões de requirements.txt
avaliar.py                 avaliação contra o conjunto de referência
robustez.py                score sob perturbação dos documentos
generalizacao.py           desempenho documento a documento
contraprova.py             avaliação contra outra versão do conjunto
ablacao.py                 valor de cada regra
corpus.py                  auditoria dos padrões contra os acórdãos do acervo
comparar.py                diferença de comportamento contra uma versão anterior
notebook_kaggle.py         célula do notebook do Kaggle
empacotar.py               zip do dataset do Kaggle
```

O artefato oficial da solução é um JSON por documento, de onde o
`submission.csv` sai pelo conversor da organização. Um teste trava que o CSV
escrito direto é byte a byte o que o conversor produziria a partir dos JSONs.

## Modelo

[`Qwen/Qwen3-8B`](https://huggingface.co/Qwen/Qwen3-8B), Apache 2.0, revisão
fixa `b968826d9c46dd6066d109eabc6255188de91218`. Decodificação determinística
(greedy, `do_sample=False`), *thinking mode* desligado, inferência em lote.

Escolhido sobre Llama 3.1 8B e Gemma 3 por licença: ambas trazem termos
próprios com restrições de atribuição e nomenclatura, enquanto as regras do
desafio exigem ferramentas de pesos e código abertos.

## Executar

### Ponto de entrada

```bash
# uma vez, com internet, para baixar os pesos (16 GB, revisão fixa):
python baixar_modelo.py

# execução:
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida>
```

Grava o `submission.csv` no formato das submissões e, ao lado dele, os JSONs do
contrato. Os três caminhos chegam por argumento: nada depende de caminho
absoluto nem de arquivo que exista só na máquina de desenvolvimento.

A execução é **offline**: `run.sh` exporta `HF_HUB_OFFLINE=1`, e o carregamento
usa `local_files_only=True`. Faltando os pesos em `modelo/`, a falha é imediata
e indica o comando a rodar.

**Hardware.** Em bfloat16 o modelo ocupa cerca de 16,4 GB e cabe numa placa de
24 GB. `device_map="auto"` usa a placa única quando há uma e reparte entre as
duas quando há duas, de modo que o mesmo código serve à avaliação e ao Kaggle
(T4 ×2, onde repartir é obrigatório).

**Determinismo.** Decodificação gulosa, sem amostragem, e `PYTHONHASHSEED`
fixo. O modelo é consultado em cerca de 1,6% das citações do conjunto de
desenvolvimento; a extração e o restante da resolução são determinísticos.

### Docker

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

A construção da imagem roda a suíte de regressão. As versões estão fixas em
`requirements.txt`.

### Desenvolvimento

Os dados da competição não estão versionados (ver `.gitignore`). Baixe
`desafio1_bracis.db`, `txt/`, o `goldenset` e `kaggle_metric.py` da aba *Data*
da competição e coloque na raiz do projeto.

```bash
pip install -r requirements.txt

pytest tests/                    # suíte de regressão, roda em milissegundos
python avaliar.py                # avaliação determinística, sem carregar o modelo
python avaliar.py --com-modelo   # pipeline completo, requer GPU
python robustez.py               # score sob perturbação dos documentos
python generalizacao.py          # desempenho documento a documento
python corpus.py                 # forma dos trechos nos acórdãos do acervo
python contraprova.py <base>     # score contra outra versão do conjunto
python ablacao.py --base-antiga <base>
python comparar.py <revisão>     # diferença de comportamento contra outra revisão
```

`avaliar.py` imprime o score por nível, a cobertura da extração e o acerto por
caminho de resolução, marcando com `*` os caminhos que dependem do modelo.

## Generalização

O conjunto final são documentos que ninguém viu, e são estas as medidas que
guiaram o desenvolvimento, em lugar do placar nos 26 documentos distribuídos.

**Duas versões do dataset.** A organização publicou duas, e a solução marca
1,0819 na anterior e 1,1000 na final (`contraprova.py`).

**Ablação.** `ablacao.py` desativa cada regra e compara a queda nas duas bases.
A assimetria máxima é 0,0037 contra uma queda de até 0,42: nenhuma regra
depende de qual versão do conjunto a mede.

**Robustez.** `robustez.py` reaplica a métrica sobre versões perturbadas dos
documentos, preservando os spans do gabarito:

| Perturbação | Score |
|---|---|
| nenhuma | 1.1000 |
| ruído de digitalização em 2% dos algarismos | 1.0880 |
| ponto de milhar entregue como espaço | 1.0746 |
| indicador de número com o outro sinal de grau | 1.1000 |
| travessão no lugar do hífen | 1.1000 |

**Desempenho por documento.** `generalizacao.py` avalia cada documento
isoladamente: nenhum cai mais de 0,01 abaixo da referência.

**Acórdãos reais.** Os 26 documentos de referência são pareceres; os 1014
acórdãos do acervo são peças reais de cinco tribunais. `corpus.py` audita os
padrões contra eles, e `tests/` cobre o que esse gênero exercita e os
pareceres não: veículo de publicação (`DJe de 14/3/2024`), referência de autos
(`Evento 17`, `fls. 45`) e o número que acompanha o do processo, como o ano em
`Petição 45.556/2023`.

**Testes metamórficos e adversariais.** A mesma citação em sete formulações
recebe a mesma classe e o mesmo `id_canonico`; trocar a ordem de duas não
altera nenhuma; acrescentar uma nova não muda as anteriores. A bateria
adversarial cobre prosa corrente com forma de citação ("o prazo de 15 dias
úteis", "multa de 20% sobre o valor", "Sessão de 12/03/2024").

**Outro gênero na entrada.** O pipeline sobre 40 acórdãos reais como entrada
rende 7.599 citações sem exceções, com distribuição equilibrada entre as três
classes; 7,76% caem em caminhos que dependem do modelo ou de sinal indireto,
contra 1,6% nos pareceres.

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados da competição pertencem à
organização do desafio e não são redistribuídos aqui.
