"""
Prompts versionados.

Cada prompt é um registro imutável: texto, versão e a anotação do que mudou
em relação à versão anterior. A versão entra no relatório de avaliação, de
modo que um resultado sempre possa ser reproduzido com o prompt exato que o
produziu.

Alterar o texto de um prompt exige criar uma versão nova, nunca editar a
existente, porque a versão publicada já foi usada para gerar resultados.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """Prompt de sistema identificado por nome e versão."""

    nome: str
    versao: str
    texto: str
    nota: str

    @property
    def identificador(self) -> str:
        return f"{self.nome}@{self.versao}"


def registrar(prompts: tuple[Prompt, ...]) -> Prompt:
    """Versão vigente de uma família de prompts, que é a última da tupla.

    O histórico permanece acessível para comparação e para reproduzir um
    resultado anterior.
    """
    if not prompts:
        raise ValueError("uma família de prompts precisa de ao menos uma versão")
    return prompts[-1]
