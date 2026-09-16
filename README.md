# Caça-Alucinações · BRACIS 2026 × Jusbrasil

Verificação de citações jurídicas em pareceres gerados por IA. Dado um
documento, localizar cada citação de jurisprudência ou de lei e classificá-la
como `real` (com o `id_canonico` do registro), `inventada` ou `incompleta`.

**Resultado na competição: 1.09803** (métrica oficial, sobre a versão anterior do dataset).

O leaderboard atual roda sobre a amostra de treino distribuída, e reinicia
quando o conjunto final for ativado: a classificação sai de 40% públicos e
60% privados de documentos que ninguém viu. O que vale, portanto, é
generalizar, e não pontuar nestes 26 documentos.

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

**A extração não consulta o modelo.** Os padrões alcançam as 192 citações do
conjunto de referência.
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

**Número que nenhum registro traz no cabeçalho é decidido pela espécie do
recurso.** Ele consta do acervo apenas dentro de fundamentações, e a espécie
diz se existe processo com ele: um número que só aparece como mandado de
segurança não responde por uma reclamação, mas um que aparece transcrito
num recurso de revista responde por um agravo naquele mesmo recurso, porque
as duas espécies são o mesmo processo em fases distintas. É o que distingue
uma referência a processo inexistente de uma referência legítima, já que
ambas encontram documentos na busca por texto.

**Uma referência só é citação quando aponta um julgado determinado.** O órgão
sozinho descreve um conjunto difuso: "reiterados precedentes do Superior
Tribunal de Justiça" e "a jurisprudência pacífica desta Corte" não apontam
acórdão nenhum e não são citação. O que estreita a referência a um julgado é
o ano ou o relator, e a classe `incompleta` reúne justamente as que trazem
órgão e um dos dois, sem o número.

**O dono do número é quem o apresenta como os autos que julga.** A fórmula de
autuação abre o acórdão ("Vistos, relatados e discutidos estes autos de
Recurso de Revista nº X"), e onde ela falta o número está sendo transcrito de
outro feito. É o que resolve dois acórdãos que trazem o mesmo número.

**A espécie do recurso separa feitos de mesmo número.** O acórdão anuncia no
cabeçalho a espécie que julga, e a sigla da citação nomeia a mesma espécie
abreviada: "AgARR" é o agravo em recurso de revista com agravo, não o agravo
de instrumento que o precedeu, ainda que os dois tramitem com aquele número.
Casar as duas resolve tanto a disputa entre registros quanto a pergunta de
se o processo citado existe.

**O modelo decide só o que a estrutura não decide.** Ele é consultado quando
dois processos foram autuados com o mesmo número e diferem apenas na espécie
do recurso, caso em que só a leitura dos cabeçalhos separa um do outro. No
conjunto de referência isso ocorre uma vez em 195 citações, e é a única
consulta ao modelo em todo o pipeline. Trocar a resposta por qualquer valor
fixo muda o score em menos de 0.007.

**A confiança declarada é medida, não estimada.** Cada caminho tem a sua,
calibrada pela taxa de acerto observada. O bônus mede a distância entre a
confiança e o acerto efetivo, de modo que rebaixá-la abaixo da taxa medida
custa tanto quanto exagerá-la. Todos os caminhos acertam integralmente o
conjunto de referência, e o valor que maximiza o bônus é 0,99: fica acima de
0,98 quando tudo acerta e à frente de 1,00 quando três predições falham,
porque declarar certeza absoluta e errar custa o dobro.

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
  llm_qwen.py              carregamento e geração com o Qwen3-8B
  prompts/                 prompts versionados, com histórico e notas
tests/                     suíte de regressão, sem banco e sem modelo
notebook_kaggle.py         célula única que gera submission.csv no Kaggle
avaliar.py                 avaliação reprodutível contra o conjunto de referência
robustez.py                score sob perturbação dos documentos
generalizacao.py           desempenho por documento, para expor ajuste excessivo
contraprova.py             avaliação contra uma base diferente da instalada
ablacao.py                 valor de cada regra nas duas bases, para expor assimetria
corpus.py                  auditoria dos padrões contra os acórdãos reais do acervo
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
python generalizacao.py          # desempenho documento a documento
python corpus.py                 # forma dos trechos nos acórdãos reais do acervo
python contraprova.py <base>     # score contra outra versão do conjunto
python ablacao.py --base-antiga <base>   # valor de cada regra nas duas bases
```

`avaliar.py` imprime o score por nível, a cobertura da extração e o acerto por
caminho de resolução, marcando com `*` os caminhos que dependem do modelo.
`--json relatorio.json` grava o relatório completo com commit e versões de
prompt.

`comparar.py <revisão>` mostra a diferença de comportamento contra uma
versão anterior do próprio repositório, em duas frentes: as predições de
cada documento e os prompts que seriam enviados ao modelo. Comparar apenas
as predições esconde uma mudança de prompt, que altera o resultado da
submissão sem alterar nada localmente. Rode antes de submeter, contra a
revisão do melhor resultado conhecido:

```bash
python comparar.py v1.0.0
```

### A contraprova de duas bases

A organização publicou duas versões do dataset, e a diferença entre elas é
a melhor prova de generalização disponível. Medido com `contraprova.py`:

| código | base anterior | base final |
|---|---|---|
| antes do ajuste | 0,9924 | 0,9759 |
| **depois** | **1,0819** | **1,0999** |

A versão anterior marcava 1,09803 no leaderboard e não passava de 0,99 em
nenhuma das duas bases reais. A diferença vinha de um gabarito que ela
própria havia inferido: 29 citações reconstruídas a partir de lacunas na
numeração, nenhuma das quais existe. As lacunas eram remoções deliberadas.

A lição ficou no método: uma hipótese sobre o gabarito que o próprio
sistema usa para se medir não é verificável, e o leaderboard da fase de
treino a recompensava. O que restou como medida honesta é pontuar bem em
bases que não foram usadas para escrever as regras.

`generalizacao.py` avalia cada documento isoladamente e compara com o
conjunto inteiro. Uma parte que caia muito abaixo da referência indicaria
que as regras se apoiam em traços de documentos específicos. A suíte
`tests/test_generalizacao.py` complementa a medida pelo outro lado, com
formas plausíveis e ausentes dos 26 documentos distribuídos.

`robustez.py` reaplica a métrica sobre versões perturbadas dos documentos,
preservando os spans do gabarito. É a medida que importa para um conjunto de
avaliação cego, cujo ruído não está no conjunto de referência:

| Perturbação | Score |
|---|---|
| nenhuma | 1.0999 |
| ruído de digitalização em 2% dos algarismos | 1.0879 |
| ponto de milhar entregue como espaço | 1.0746 |
| indicador de número com o outro sinal de grau | 1.0999 |
| travessão no lugar do hífen | 1.0999 |

### Ablação: o que cada regra vale nas duas bases

Uma regra que capturou o critério do desafio vale o mesmo nas duas versões
publicadas; uma ajustada à amostra vale muito numa e pouco na outra.
`ablacao.py` desativa cada regra e compara as duas quedas:

| Regra desativada | Queda (final) | Queda (anterior) | Assimetria |
|---|---|---|---|
| citação com identificador | 0,4205 | 0,4171 | 0,0034 |
| prosa: termo jurisprudencial | 0,1588 | 0,1550 | 0,0037 |
| artigo de lei | 0,1175 | 0,1160 | 0,0015 |
| prosa: espécie e órgão | 0,0509 | 0,0506 | 0,0003 |
| prosa: espécie e ano | 0,0324 | 0,0322 | 0,0002 |
| tema de repercussão | 0,0076 | 0,0076 | 0,0000 |
| súmula | 0,0028 | 0,0029 | 0,0001 |
| filtro de número administrativo | 0,0000 | 0,0000 | 0,0000 |

A assimetria máxima é 0,0037 contra uma queda de até 0,42: nenhuma regra
depende de qual versão do conjunto a mede. O filtro de número
administrativo cai a zero porque nenhuma das bases o exercita, e mesmo
assim descarta cinco inscrições da OAB e quatro falsos positivos num
documento adversarial; é defesa, não código morto.

### Auditoria contra os acórdãos reais

Os 26 documentos de referência são pareceres redigidos para o desafio; os
1014 acórdãos do acervo são peças reais dos cinco tribunais, e nenhuma
regra foi escrita olhando para eles. `corpus.py` mede a forma dos trechos
capturados ali, e foi o que expôs duas classes que os pareceres não
exercitam porque pertencem ao outro gênero textual:

| Classe | Exemplo | Custo medido |
|---|---|---|
| veículo de publicação | `DJe de 14/3/2024`, `DEJT 03/02/2012` | 0,045 a 0,108 |
| referência de autos | `Evento 17`, `ID 61582938`, `fls. 45` | 0,166 |

As duas juntas custavam 0,2555, injetadas nos 26 documentos. Ambas têm a
forma de identificador sem apontar julgado algum, e a resolução as dava por
inventadas com confiança 0,99, que é o pior tipo de falso positivo para a
métrica. Depois do filtro, os trechos abertos por rótulo indevido caíram de
cerca de 4.000 para 5 em 22.577 (0,022%), e o score das duas bases não se
moveu.

A mesma auditoria mostrou que o artigo definido em início de período
(`O AgInt no AREsp 123456/SP`) entrava no span. Em 121 das 192 citações do
gabarito há um artigo colado ao span e nenhuma o inclui; com identificador
curto o excedente derruba a sobreposição abaixo de 0,5 e a citação é
contada como perdida. A distinção agora é morfológica, não enumerada: o
artigo, o verbo com pronome (`Registre-se`) e o advérbio em `-mente`
introduzem a citação sem pertencer a ela.

Requer GPU para o pipeline completo. Em bfloat16 o modelo ocupa cerca de
16.4 GB; no Kaggle (T4 ×2) é distribuído entre as duas GPUs com
`device_map="balanced"`.

## Licença

Código sob licença MIT (ver `LICENSE`). Os dados da competição pertencem à
organização do desafio e não são redistribuídos aqui.
