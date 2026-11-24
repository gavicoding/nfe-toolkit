"""Organize a folder of XML files into ``destination/YYYY/MM/`` by access key.

Planning and applying are separate steps: :func:`planejar` only reads files
and returns a :class:`Plano`; :func:`aplicar` moves or copies them. Existing
files are never overwritten; a repeated name gets a ``_2``, ``_3``... suffix.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .chave import decompor
from .erros import NfeToolkitError, NotaInvalidaError
from .xml import ler_nota, listar_xmls

_ANO = re.compile(r"[0-9]{4}")
_MES = re.compile(r"[0-9]{2}")


@dataclass(frozen=True)
class Movimento:
    origem: Path
    destino: Path
    chave: str


@dataclass(frozen=True)
class Duplicado:
    arquivo: Path
    chave: str
    original: Path


@dataclass(frozen=True)
class Falha:
    arquivo: Path
    motivo: str


@dataclass
class Plano:
    origem: Path
    destino: Path
    movimentos: list[Movimento] = field(default_factory=list)
    duplicados: list[Duplicado] = field(default_factory=list)
    falhas: list[Falha] = field(default_factory=list)


@dataclass
class Resultado:
    feitos: list[Movimento] = field(default_factory=list)
    falhas: list[Falha] = field(default_factory=list)


def planejar(origem: str | Path, destino: str | Path, recursivo: bool = True) -> Plano:
    """Build the plan without touching any file.

    Files already organized under ``destino`` are indexed first, so a loose
    file whose key is already there is reported as a duplicate.
    """
    origem = Path(origem).resolve()
    destino = Path(destino).resolve()
    if not origem.is_dir():
        raise NfeToolkitError(f"source folder not found: {origem}")
    if destino.exists() and not destino.is_dir():
        raise NfeToolkitError(f"destination is not a folder: {destino}")

    plano = Plano(origem=origem, destino=destino)
    vistos: dict[str, Path] = {}
    reservados: set[str] = set()

    if destino.is_dir():
        for arquivo in listar_xmls(destino):
            if not _ja_organizado(arquivo, destino):
                continue
            reservados.add(_chave_nome(arquivo))
            try:
                nota = ler_nota(arquivo)
            except (NotaInvalidaError, OSError):
                continue
            if nota.chave_valida:
                vistos.setdefault(nota.chave, arquivo)

    for arquivo in listar_xmls(origem, recursivo):
        if _ja_organizado(arquivo, destino):
            continue
        try:
            nota = ler_nota(arquivo)
        except NotaInvalidaError as erro:
            plano.falhas.append(Falha(arquivo, _sem_prefixo(str(erro), arquivo)))
            continue
        except OSError as erro:
            plano.falhas.append(Falha(arquivo, f"cannot read file ({erro.strerror or erro})"))
            continue
        if not nota.chave_valida:
            plano.falhas.append(Falha(arquivo, f"invalid access key {nota.chave}"))
            continue
        if nota.chave in vistos:
            plano.duplicados.append(Duplicado(arquivo, nota.chave, vistos[nota.chave]))
            continue
        vistos[nota.chave] = arquivo

        info = decompor(nota.chave)
        pasta = destino / f"{info.ano:04d}" / f"{info.mes:02d}"
        alvo = _nome_livre(pasta / arquivo.name, reservados)
        reservados.add(_chave_nome(alvo))
        plano.movimentos.append(Movimento(arquivo, alvo, nota.chave))

    return plano


def aplicar(plano: Plano, copiar: bool = False) -> Resultado:
    """Execute a plan. Each file is handled on its own; errors do not stop the run."""
    resultado = Resultado()
    for mov in plano.movimentos:
        try:
            mov.destino.parent.mkdir(parents=True, exist_ok=True)
            alvo = _nome_livre(mov.destino, set())
            _copiar_sem_sobrescrever(mov.origem, alvo)
            if not copiar:
                mov.origem.unlink()
        except OSError as erro:
            resultado.falhas.append(Falha(mov.origem, str(erro)))
            continue
        resultado.feitos.append(Movimento(mov.origem, alvo, mov.chave))
    return resultado


def _copiar_sem_sobrescrever(origem: Path, destino: Path) -> None:
    # "xb" fails if the target appeared in the meantime, so nothing is overwritten.
    with origem.open("rb") as entrada, destino.open("xb") as saida:
        try:
            shutil.copyfileobj(entrada, saida)
        except OSError:
            saida.close()
            destino.unlink(missing_ok=True)
            raise
    shutil.copystat(origem, destino)


def _nome_livre(alvo: Path, reservados: set[str]) -> Path:
    candidato = alvo
    n = 2
    while candidato.exists() or _chave_nome(candidato) in reservados:
        candidato = alvo.with_name(f"{alvo.stem}_{n}{alvo.suffix}")
        n += 1
    return candidato


def _chave_nome(caminho: Path) -> str:
    return os.path.normcase(str(caminho))


def _ja_organizado(arquivo: Path, destino: Path) -> bool:
    try:
        partes = arquivo.resolve().relative_to(destino).parts
    except ValueError:
        return False
    return len(partes) == 3 and bool(_ANO.fullmatch(partes[0]) and _MES.fullmatch(partes[1]))


def _sem_prefixo(mensagem: str, arquivo: Path) -> str:
    prefixo = f"{arquivo}: "
    return mensagem[len(prefixo) :] if mensagem.startswith(prefixo) else mensagem
