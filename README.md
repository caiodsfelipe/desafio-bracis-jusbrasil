# Caça-Alucinações — BRACIS 2026 × Jusbrasil

Verificação de citações jurídicas em pareceres gerados por IA. Dado um
documento, localizar cada citação de jurisprudência ou de lei e classificá-la
como `real` (com o `id_canonico` do registro), `inventada` ou `incompleta`.

## Abordagem

Pipeline *retrieve-then-verify*, não RAG semântico. Citações jurídicas são
identificadores formais: quem decide se um processo existe é uma busca exata
no acervo, não similaridade de embedding — dois números de processo quase
idênticos são documentos diferentes, e é justamente aí que a métrica pune
mais (confundir `inventada` com `real`).

```
texto do documento
   ├─ regex estrutural ─┐
   └─ LLM (prosa livre) ─┴─→ mesclagem por IoU ≥ 0.5 → candidatos
                                                          │
                    ┌─────────────────────────────────────┤
        súmula/artigo?                              acórdão?
                    │                                     │
        índice normativo                    FTS5 pelo identificador
        (18 registros, por                  normalizado → "é o dono do
         número + diploma)                   processo?" (LLM, em lote)
                    │                                     │
                    └──────────→ contagem de candidatos ←─┘
                         1 = real · 0 = inventada · 2+ = incompleta
```

### Decisões que moldaram o desenho

- **O span vem sempre do texto original.** O LLM copia o trecho; o código
  procura essa string de volta no documento e descarta o que não for
  encontrado. Tolerância só a espaço em branco — o nível 2 injeta ruído de
  OCR de propósito (`0↔O`, `1↔l`, `5↔S`, `G→6`, `g→9`), e um modelo
  "corrigindo" isso produziria um span que não corresponde ao original.
- **Normalização é local ao span**, nunca global: trocar `O` por `0` no
  documento inteiro destruiria palavras comuns.
- **Súmulas e artigos não resolvem por FTS.** Buscar "Súmula 83 do STJ" no
  acervo devolve os acórdãos que a mencionam, nunca a súmula. Os 18 registros
  normativos são indexados à parte, por número **e diploma** — o mesmo número
  de artigo existe em diplomas diferentes (art. 290 é real no CPM e inventado
  na Constituição).
- **"É o dono do processo ou só cita?"** decidido pelo LLM. Limiar de posição
  não generaliza (no TST o próprio número aparece a dezenas de milhares de
  caracteres do início) e regra textual gera falso positivo (citar precedente
  também menciona "relator" perto do número).
- **Inferência em lote.** As perguntas de dono/citação de um documento inteiro
  vão numa passada só, deduplicadas; a resposta útil tem 1 token, então em
  série o custo seria quase todo overhead.

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `regex_extracao.py` | Extração estrutural (sigla + identificador) |
| `prompt_extracao.py` | Extração via LLM, inclusive citações em prosa |
| `schema_extracao.py` | Schema Pydantic que valida a saída do LLM |
| `verificacao_substring.py` | Reancora o trecho do LLM no texto original |
| `extracao.py` | Mescla as duas fontes e deduplica por IoU |
| `normalizacao.py` | Normaliza o identificador dentro do span |
| `indice_normativo.py` | Índice dos 18 registros de súmula/dispositivo |
| `prompt_dono.py` | Classificação dono vs. citação (em lote) |
| `resolucao.py` | Busca no acervo, roteamento e decisão de classe |
| `llm_qwen.py` | Carregamento e geração com o Qwen3-8B |

## Modelo

[`Qwen/Qwen3-8B`](https://huggingface.co/Qwen/Qwen3-8B), Apache 2.0, revisão
fixa `b968826d9c46dd6066d109eabc6255188de91218`. Decodificação determinística
(greedy, `do_sample=False`) e *thinking mode* desligado.

Escolhido sobre Llama 3.1 8B e Gemma 3 por licença: ambas trazem termos
próprios com restrições de atribuição e nomenclatura, enquanto as regras do
desafio exigem ferramentas de pesos e código abertos.

## Executar

Os dados da competição não estão versionados (ver `.gitignore`). Baixe
`desafio1_bracis.db`, `txt/` e `goldenset.csv` da aba *Data* da competição e
coloque na raiz do projeto.

```bash
pip install torch transformers pydantic
python -c "
import sqlite3, sys; sys.path.insert(0, 'src')
from llm_qwen import QwenClassificador
from prompt_extracao import extrair_citacoes
from extracao import extrair_todos
from indice_normativo import construir_indice
from resolucao import resolver_citacoes

con = sqlite3.connect('desafio1_bracis.db')
indice = construir_indice(con)
qwen = QwenClassificador()
texto = open('txt/gen_n1_001.txt', encoding='utf-8').read()
candidatos = extrair_todos(texto, extrair_citacoes(qwen, texto))
for c, (classe, id_canonico) in zip(candidatos, resolver_citacoes(con, qwen, indice, candidatos)):
    print(c.inicio, c.fim, classe, id_canonico, repr(c.trecho[:50]))
"
```

Requer GPU. Em bfloat16 o modelo ocupa ~16.4GB, então numa placa de 16GB use
quantização 4-bit; no Kaggle (T4 ×2) ele é distribuído entre as duas GPUs com
`device_map="balanced"`.
