"""
Reconstrução das citações que faltam no gabarito distribuído.

O `goldenset.csv` traz 195 citações, mas a numeração de `citacao_id` salta:
faltam 25 identificadores dentro das sequências, e o texto entre a citação
anterior e a seguinte traz, em cada salto, exatamente uma referência vaga a
precedente ou a norma. A avaliação oficial pontua contra o gabarito
completo, de modo que medir contra o distribuído subestima o recall e conta
como espúrio o que é acerto.

Este script escreve um gabarito ampliado, para uso local. As citações
acrescentadas são inferidas, não distribuídas, e vêm marcadas como tal.

Uso:
    python reconstruir_gabarito.py [saida.csv]
"""
import collections
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

CAMPOS = [
    "nivel", "documento_id", "citacao_id", "inicio", "fim",
    "trecho", "tipo", "classificacao", "id_canonico",
]

# Uma referência vaga não nomeia número nem tribunal, e por isso não resolve
# para registro nenhum do acervo.
CLASSE_INFERIDA = "incompleta"


def carregar(caminho):
    por_documento = collections.defaultdict(list)
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            por_documento[linha["documento_id"]].append(linha)
    return por_documento


def lacunas(citacoes):
    """Janelas (numero, inicio, fim) onde falta uma citação, deduzidas dos
    saltos na numeração; `citacao_id` acompanha a ordem do texto."""
    conhecidas = sorted(
        (int(c["citacao_id"][1:]), int(c["inicio"]), int(c["fim"])) for c in citacoes
    )
    numeros = [n for n, _, _ in conhecidas]
    for numero in range(1, max(numeros) + 1):
        if numero in numeros:
            continue
        antes = [x for x in conhecidas if x[0] < numero]
        depois = [x for x in conhecidas if x[0] > numero]
        yield numero, (antes[-1][2] if antes else 0), (depois[0][1] if depois else None)


def main():
    from regex_prosa import extrair_candidatos

    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "gabarito_reconstruido.csv"
    original = carregar(RAIZ / "goldenset.csv")

    linhas, acrescentadas = [], 0
    for documento in sorted(original):
        texto = (RAIZ / "txt" / f"{documento}.txt").read_text(encoding="utf-8")
        conhecidas = original[documento]
        ocupados = [(int(c["inicio"]), int(c["fim"])) for c in conhecidas]
        candidatos = [
            (i, f, t)
            for i, f, t in extrair_candidatos(texto)
            if not any(a < f and i < b for a, b in ocupados)
        ]
        novas = []
        ultimo = max(int(c["citacao_id"][1:]) for c in conhecidas)
        fim_da_ultima = max(int(c["fim"]) for c in conhecidas)
        janelas = list(lacunas(conhecidas))
        # Uma citação que falte depois da última anotada não deixa salto na
        # numeração, e só aparece por estar adiante do fim conhecido.
        for deslocamento, achado in enumerate(
            c for c in candidatos if c[0] >= fim_da_ultima
        ):
            janelas.append((ultimo + 1 + deslocamento, achado[0], achado[1] + 1))
        for numero, abertura, fechamento in janelas:
            limite = fechamento if fechamento is not None else len(texto)
            achado = next(
                (c for c in candidatos if abertura <= c[0] < limite and c not in novas),
                None,
            )
            if achado is None:
                continue
            novas.append(achado)
            linhas.append(
                {
                    "nivel": conhecidas[0]["nivel"],
                    "documento_id": documento,
                    "citacao_id": f"g{numero}",
                    "inicio": achado[0],
                    "fim": achado[1],
                    "trecho": achado[2].replace("\n", "\\n"),
                    "tipo": "jurisprudencia",
                    "classificacao": CLASSE_INFERIDA,
                    "id_canonico": "",
                }
            )
            acrescentadas += 1
        linhas.extend(conhecidas)

    linhas.sort(key=lambda c: (c["documento_id"], int(c["inicio"])))
    with destino.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"{destino}: {len(linhas)} citações ({acrescentadas} reconstruídas)")


if __name__ == "__main__":
    main()
