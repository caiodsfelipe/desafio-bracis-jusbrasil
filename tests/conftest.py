"""Torna os módulos de `src/` importáveis pelos testes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
