"""Exceptions raised by nfe_toolkit."""

from __future__ import annotations


class NfeToolkitError(Exception):
    """Base class for every error raised by this package."""


class ChaveInvalidaError(NfeToolkitError, ValueError):
    """The access key (chave de acesso) is malformed or has a wrong check digit."""


class NotaInvalidaError(NfeToolkitError, ValueError):
    """The file is not a readable NF-e/NFC-e XML document."""


class ListaInvalidaError(NfeToolkitError, ValueError):
    """The list of expected access keys could not be read."""
