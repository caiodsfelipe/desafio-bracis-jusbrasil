"""
Auditoria dos padrões contra os acórdãos do acervo.

Os 26 documentos do conjunto de referência são pareceres redigidos para o
desafio; os 1014 acórdãos do acervo são peças reais dos cinco tribunais.
Nenhuma regra foi escrita olhando para eles, o que os torna o corpus de
validação mais honesto disponível: o que os padrões capturam ali revela o
que capturariam num documento oculto, sem que nenhum ajuste à amostra possa
mascarar o resultado.

A medida não é de acerto, porque o acervo não traz gabarito. É de forma: a
primeira palavra de cada trecho capturado diz se o padrão delimitou uma
citação ou arrastou junto o que a antecede. Um rótulo frequente no topo da
contagem é um falso positivo sistemático.

Foi assim que apareceram duas classes que o conjunto de referência não
exercita, porque acórdão e parecer são gêneros distintos:

    veículo de publicação   "DJe de 14/3/2024", "DEJT 03/02/2012"
    referência de autos     "Evento 17", "ID 61582938", "fls. 45"

Ambas têm a forma de identificador sem apontar julgado algum, e a resolução
as daria por inventadas com confiança alta, que é o pior tipo de falso
positivo para a métrica.

O que resta capturar são os casos em que a digitalização intercalou texto
entre o rótulo e o número ("DJe DIVULG 14.4.2020"), 0,022% dos trechos.
Alargar a ligação para alcançá-los faria o filtro atravessar palavras e
descartar citação legítima vizinha, e o custo excede o ganho.

Uso:
    python corpus.py
    python corpus.py --amostra 300
"""

import argparse
import collections
import random
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

# Amostra suficiente para que um falso positivo sistemático apareça na
# contagem, e pequena o bastante para a varredura terminar rápido.
_ACORDAOS_AMOSTRADOS = 120
_SEMENTE = 0

# O que nunca abre uma citação: o artigo e o articulador que a introduzem,
# o veículo que publicou o acórdão e a peça numerada dentro dos autos.
_ABERTURAS_INDEVIDAS = frozenset(
    {
        "O", "A", "Os", "As",
        "Conforme", "Segundo", "Vide", "Todavia", "Contudo", "Entretanto",
        "Assim", "Ainda", "Também", "Ademais", "Outrossim", "Portanto",
        "DJ", "DJe", "DJE", "DEJT", "DOU", "DOE",
        "Evento", "ID", "Seq", "fls", "fls.", "doc", "doc.", "Anexo", "Mov",
    }
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acervo", default=str(RAIZ / "desafio1_bracis.db"))
    parser.add_argument("--amostra", type=int, default=_ACORDAOS_AMOSTRADOS)
    parser.add_argument("--topo", type=int, default=20)
    argumentos = parser.parse_args()

    from extracao import extrair_todos

    con = sqlite3.connect(argumentos.acervo)
    acordaos = con.execute("select tribunal, texto from documentos").fetchall()
    amostra = random.Random(_SEMENTE).sample(
        acordaos, min(argumentos.amostra, len(acordaos))
    )

    primeira_palavra = collections.Counter()
    por_tribunal = collections.Counter()
    exemplos = collections.defaultdict(list)
    total = 0
    for tribunal, texto in amostra:
        for ocorrencia in extrair_todos(texto):
            total += 1
            por_tribunal[tribunal or "sem registro"] += 1
            palavras = ocorrencia.trecho.split()
            abertura = palavras[0] if palavras else ""
            primeira_palavra[abertura] += 1
            if abertura in _ABERTURAS_INDEVIDAS and len(exemplos[abertura]) < 3:
                exemplos[abertura].append(ocorrencia.trecho[:64])

    print(f"acórdãos amostrados  {len(amostra)} de {len(acordaos)}")
    print(f"trechos capturados   {total}")
    print("\npor tribunal")
    for tribunal, quantidade in por_tribunal.most_common():
        print(f"  {tribunal:<14}{quantidade}")

    print(f"\naberturas mais comuns (topo {argumentos.topo})")
    for palavra, quantidade in primeira_palavra.most_common(argumentos.topo):
        print(f"  {quantidade:>6}  {palavra}")

    indevidas = sum(
        quantidade
        for palavra, quantidade in primeira_palavra.items()
        if palavra in _ABERTURAS_INDEVIDAS
    )
    proporcao = 100 * indevidas / total if total else 0.0
    print(f"\ntrechos abertos por palavra indevida: {indevidas} ({proporcao:.3f}%)")
    for palavra, amostras in sorted(exemplos.items()):
        print(f"  {palavra}")
        for trecho in amostras:
            print(f"      {trecho!r}")


if __name__ == "__main__":
    raise SystemExit(main())
