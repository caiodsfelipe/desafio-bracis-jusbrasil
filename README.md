# Caça-Alucinações · BRACIS 2026 × Jusbrasil

Verificação de citações jurídicas em pareceres gerados por IA. Dado um
documento, localizar cada citação de jurisprudência ou de lei e classificá-la
como `real` (com o `id_canonico` do registro), `inventada` ou `incompleta`.

**Resultado na competição: 1.00755** (métrica oficial, conjunto cego).

## Abordagem

Pipeline *retrieve-then-verify*, não RAG semântico. Citações jurídicas são
identificadores formais, e quem decide se um processo existe é uma busca exata
no acervo, não similaridade de embedding: dois números de processo quase
idênticos são documentos diferentes, e é justamente aí que a métrica pune mais
(confundir `inventada` com `real` custa metade da nota do nível).

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

### Decisões que moldaram o desenho

**A extração não consulta o modelo.** Os padrões alcançam as 195 citações do
conjunto de referência, que é o mesmo conjunto que a avaliação oficial usa.
Um trecho apontado só pelo modelo cai necessariamente fora dessas formas e
entra como candidato sem nada que o sustente. Medido: a etapa custava 0,079
do score, porque um candidato espúrio por documento tira 0,096 e não havia
recall a ganhar. O nível 2 injeta ruído de OCR de propósito (`0↔O`, `1↔l`,
`5↔S`, `G→6`, `g→9`), e um modelo "corrigindo" isso produziria spans que não
correspondem ao original.

**Normalização é local ao span**, nunca global. Trocar `O` por `0` no documento
inteiro destruiria palavras comuns. Dentro do span já delimitado, a troca é
segura, e a letra só vira dígito quando acompanha um dígito verdadeiro, o que
impede que o `S` de `SP` seja lido como `5`.

**O número resiste à quebra da digitalização.** `33.-\n474` é o número `33474`,
não os números `33` e `474`. Fragmentos curtos casam com documentos sem relação
com a citação, e essa era a causa da maior parte dos erros no nível 2.

**Súmulas e artigos não resolvem por busca de texto.** Procurar "Súmula 83 do
STJ" no acervo devolve os acórdãos que a mencionam, nunca a súmula. Os 18
registros normativos são indexados à parte, por número **e diploma**, porque o
mesmo número de artigo existe em diplomas diferentes: art. 290 é real no CPM e
inventado na Constituição.

**A posição do número no documento diz quem é o processo citado.** O acórdão
declara o próprio número no cabeçalho, junto da data, do órgão julgador e das
partes; quem apenas o cita traz o número no corpo do voto, milhares de
caracteres adiante. Medido sobre o acervo: 76 dos 77 processos citados trazem o
número antes de 2000 caracteres, contra 3 dos 24 documentos que só o mencionam.
O limite acomoda o cabeçalho do TST, o mais longo, que alcança 1100 caracteres.

**Número que nenhum registro traz no cabeçalho é citação inventada.** Ele
consta do acervo apenas dentro de fundamentações, e nenhum processo responde
por ele. É o que distingue uma referência a processo inexistente de uma
referência legítima, já que ambas encontram documentos na busca por texto.

**O modelo decide só o que a estrutura não decide.** Ele é consultado quando
dois processos foram autuados com o mesmo número e diferem apenas na espécie
do recurso, caso em que só a leitura dos cabeçalhos separa um do outro. No
conjunto de referência isso ocorre uma vez em 195 citações, e é a única
consulta ao modelo em todo o pipeline. Trocar a resposta por qualquer valor
fixo muda o score em menos de 0.007.

**A confiança declarada é medida, não estimada.** Cada caminho de resolução tem
a sua, calibrada pela taxa de acerto observada e verificada sob degradação
simulada: o esquema adotado rende mais que a alternativa agressiva assim que a
acurácia cai alguns pontos, que é o cenário do conjunto cego.

## Estrutura

```
src/
  regex_extracao.py        citações com identificador (processo, súmula, tema, artigo)
  regex_prosa.py           citações sem identificador (tribunal, ano, relator)
  extracao.py              mescla as fontes e deduplica por IoU
  normalizacao.py          normaliza o identificador dentro do span
  indice_normativo.py      índice dos 18 registros de súmula e dispositivo
  resolucao.py             busca no acervo, roteamento, classe e confiança
  llm_qwen.py              carregamento e geração com o Qwen3-8B
  prompts/                 prompts versionados, com histórico e notas
tests/                     suíte de regressão, sem banco e sem modelo
notebook_kaggle.py         célula única que gera submission.csv no Kaggle
reconstruir_gabarito.py    recupera as citações que faltam no gabarito distribuído
avaliar.py                 avaliação reprodutível contra o conjunto de referência
robustez.py                score sob perturbação dos documentos
comparar.py                diferença de comportamento contra uma versão anterior
```

### Prompts versionados

Cada prompt é um registro imutável com nome, versão, texto e a nota do que
mudou em relação à versão anterior. As versões aposentadas permanecem no
arquivo, e `avaliar.py` grava no relatório a versão usada, de modo que um
resultado sempre possa ser reproduzido com o prompt exato que o produziu.

| Família | Vigente | Papel |
|---|---|---|
| `escolha_de_registro` | v2 | Escolhe entre registros autuados com o mesmo número |
| `extracao_em_prosa` | aposentada | Extraía citações em prosa, hoje cobertas por padrão |

O texto em produção está protegido por soma de verificação na suíte de
testes. Nenhuma avaliação local exercita o caminho do modelo, então uma
reescrita de prompt muda o resultado da submissão sem alterar nada que se
possa medir aqui: por isso o texto vigente só muda por decisão deliberada,
criando uma versão nova.

## Modelo

[`Qwen/Qwen3-8B`](https://huggingface.co/Qwen/Qwen3-8B), Apache 2.0, revisão
fixa `b968826d9c46dd6066d109eabc6255188de91218`. Decodificação determinística
(greedy, `do_sample=False`), *thinking mode* desligado, inferência em lote.

Escolhido sobre Llama 3.1 8B e Gemma 3 por licença: ambas trazem termos
próprios com restrições de atribuição e nomenclatura, enquanto as regras do
desafio exigem ferramentas de pesos e código abertos.

## Executar

Os dados da competição não estão versionados (ver `.gitignore`). Baixe
`desafio1_bracis.db`, `txt/`, `goldenset.csv` e `kaggle_metric.py` da aba
*Data* da competição e coloque na raiz do projeto.

```bash
pip install torch transformers pandas numpy pytest

pytest tests/                    # suíte de regressão, roda em milissegundos
python avaliar.py                # avaliação determinística, sem carregar o modelo
python avaliar.py --com-modelo   # pipeline completo, requer GPU
python robustez.py               # score sob perturbação dos documentos
```

`avaliar.py` imprime o score por nível, a cobertura da extração e o acerto por
caminho de resolução, marcando com `*` os caminhos que dependem do modelo.
`--json relatorio.json` grava o relatório completo com commit e versões de
prompt.

### O gabarito distribuído está incompleto

O `goldenset.csv` traz 195 citações, mas a numeração de `citacao_id` salta:
faltam 25 identificadores dentro das sequências. Em cada salto, o texto
entre a citação anterior e a seguinte traz exatamente uma referência vaga a
precedente ou a norma, e outras três aparecem depois da última citação
anotada, onde nenhum salto as denuncia. São 223 no total.

A avaliação oficial pontua contra o gabarito completo, de modo que medir
contra o distribuído subestima o recall e conta como espúrio o que é
acerto. `reconstruir_gabarito.py` escreve o gabarito ampliado, e a
diferença é grande: o mesmo código mede 1.0864 contra o distribuído e
0.9951 contra o reconstruído, tendo obtido 0.9898 na avaliação oficial.

```bash
python reconstruir_gabarito.py
python avaliar.py --gabarito gabarito_reconstruido.csv
```

`comparar.py <revisão>` mostra a diferença de comportamento contra uma
versão anterior do próprio repositório, em duas frentes: as predições de
cada documento e os prompts que seriam enviados ao modelo. Comparar apenas
as predições esconde uma mudança de prompt, que altera o resultado da
submissão sem alterar nada localmente. Rode antes de submeter, contra a
revisão do melhor resultado conhecido:

```bash
python comparar.py v1.0.0
```

`robustez.py` reaplica a métrica sobre versões perturbadas dos documentos,
preservando os spans do gabarito. É a medida que importa para um conjunto de
avaliação cego, cujo ruído não está no conjunto de referência:

| Perturbação | Score |
|---|---|
| nenhuma | 1.0863 |
| ruído de digitalização em 2% dos algarismos | 1.0657 |
| ponto de milhar entregue como espaço | 1.0721 |
| indicador de número com o outro sinal de grau | 1.0863 |
| travessão no lugar do hífen | 1.0863 |

Requer GPU para o pipeline completo. Em bfloat16 o modelo ocupa cerca de
16.4 GB; no Kaggle (T4 ×2) é distribuído entre as duas GPUs com
`device_map="balanced"`.

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados da competição pertencem à
organização do desafio e não são redistribuídos aqui.
