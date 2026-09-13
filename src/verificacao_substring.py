"""
Localização, no texto original, do trecho devolvido pelo LLM.

As posições saem em codepoints Unicode com fim exclusivo. A única diferença
tolerada entre o trecho e o texto é o espaço em branco, que o modelo tende
a normalizar ao copiar. Qualquer outra divergência, uma letra ou um dígito
distinto, reprova o trecho, porque os identificadores trazem ruído de
digitalização de propósito e uma correção do modelo produziria um span que
não corresponde ao documento.

Todas as ocorrências são devolvidas; a escolha entre elas cabe à mesclagem.
"""
import re


def _regex_tolerante_a_espaco(trecho: str) -> re.Pattern:
    """Padrão que casa o trecho literalmente, exceto pelos espaços, onde
    qualquer sequência de espaço em branco é aceita."""
    pedacos = re.split(r'\s+', trecho.strip())
    pedacos_escapados = [re.escape(p) for p in pedacos if p]
    return re.compile(r'\s+'.join(pedacos_escapados))


def localizar_ocorrencias(texto: str, trecho: str) -> list[tuple[int, int]]:
    """Ocorrências do trecho no texto, como pares (inicio, fim). Lista
    vazia quando o trecho não existe no documento."""
    if not trecho or not trecho.strip():
        return []
    padrao = _regex_tolerante_a_espaco(trecho)
    return [m.span() for m in padrao.finditer(texto)]
