"""Validate, inspect, organize and reconcile NF-e/NFC-e XML files."""

from __future__ import annotations

__version__ = "1.0.0"

from .chave import ChaveInfo, calcular_dv, decompor, formatar, motivo_invalidez, validar
from .conciliar import Conciliacao, conciliar, conciliar_chaves, ler_lista
from .erros import ChaveInvalidaError, ListaInvalidaError, NfeToolkitError, NotaInvalidaError
from .organizar import Plano, aplicar, planejar
from .xml import Nota, ler_nota, ler_nota_bytes, listar_xmls

__all__ = [
    "ChaveInfo",
    "ChaveInvalidaError",
    "Conciliacao",
    "ListaInvalidaError",
    "NfeToolkitError",
    "Nota",
    "NotaInvalidaError",
    "Plano",
    "__version__",
    "aplicar",
    "calcular_dv",
    "conciliar",
    "conciliar_chaves",
    "decompor",
    "formatar",
    "ler_lista",
    "ler_nota",
    "ler_nota_bytes",
    "listar_xmls",
    "motivo_invalidez",
    "planejar",
    "validar",
]
