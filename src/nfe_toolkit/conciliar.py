"""Compare a folder of XML files with a list of expected access keys."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .chave import limpar, motivo_invalidez
from .erros import ListaInvalidaError, NfeToolkitError, NotaInvalidaError
from .xml import ler_nota, listar_xmls

#: Column names accepted as the key column in a CSV list (case-insensitive).
COLUNAS_CHAVE = ("chave", "chave_acesso", "chnfe", "key", "access_key")


@dataclass(frozen=True)
class ChaveEsperada:
    valor: str
    local: str


@dataclass(frozen=True)
class Sobra:
    chave: str
    arquivo: Path


@dataclass(frozen=True)
class Duplicada:
    chave: str
    origem: str  # "xml" or "list"
    locais: tuple[str, ...]


@dataclass(frozen=True)
class Invalida:
    origem: str  # "xml" or "list"
    local: str
    valor: str
    motivo: str


@dataclass
class Conciliacao:
    esperadas: int = 0
    encontradas: int = 0
    faltando: list[str] = field(default_factory=list)
    sobrando: list[Sobra] = field(default_factory=list)
    duplicadas: list[Duplicada] = field(default_factory=list)
    invalidas: list[Invalida] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` when no expected key is missing."""
        return not self.faltando

    @property
    def limpa(self) -> bool:
        """``True`` when there is nothing to report at all."""
        return not (self.faltando or self.sobrando or self.duplicadas or self.invalidas)

    def as_dict(self) -> dict:
        return {
            "summary": {
                "expected": self.esperadas,
                "found": self.encontradas,
                "missing": len(self.faltando),
                "extra": len(self.sobrando),
                "duplicates": len(self.duplicadas),
                "invalid": len(self.invalidas),
            },
            "missing": list(self.faltando),
            "extra": [{"key": s.chave, "file": str(s.arquivo)} for s in self.sobrando],
            "duplicates": [
                {"key": d.chave, "source": d.origem, "locations": list(d.locais)}
                for d in self.duplicadas
            ],
            "invalid": [
                {"source": i.origem, "location": i.local, "value": i.valor, "reason": i.motivo}
                for i in self.invalidas
            ],
        }


def ler_lista(path: str | Path) -> list[ChaveEsperada]:
    """Read expected keys from a ``.txt`` (one per line) or ``.csv`` file.

    In text files, blank lines and lines starting with ``#`` are ignored. CSV
    files need a header with a ``chave`` column (see :data:`COLUNAS_CHAVE`);
    the delimiter (comma, semicolon or tab) is detected.
    """
    caminho = Path(path)
    texto = _ler_texto(caminho)
    if caminho.suffix.lower() == ".csv":
        return _ler_csv(texto, caminho)
    itens = []
    for numero, linha in enumerate(texto.splitlines(), start=1):
        valor = linha.strip()
        if not valor or valor.startswith("#"):
            continue
        itens.append(ChaveEsperada(valor, f"line {numero}"))
    return itens


def conciliar(pasta: str | Path, lista: str | Path, recursivo: bool = True) -> Conciliacao:
    """Reconcile the XML files in ``pasta`` with the key list file ``lista``."""
    return conciliar_chaves(pasta, ler_lista(lista), recursivo=recursivo)


def conciliar_chaves(
    pasta: str | Path,
    esperadas: Iterable[ChaveEsperada | str],
    recursivo: bool = True,
) -> Conciliacao:
    """Reconcile a folder with keys given in memory (strings or :class:`ChaveEsperada`)."""
    base = Path(pasta)
    if not base.is_dir():
        raise NfeToolkitError(f"folder not found: {base}")
    resultado = Conciliacao()

    na_lista: dict[str, list[str]] = {}
    for indice, item in enumerate(esperadas, start=1):
        if isinstance(item, str):
            item = ChaveEsperada(item, f"item {indice}")
        motivo = motivo_invalidez(item.valor)
        if motivo:
            resultado.invalidas.append(Invalida("list", item.local, item.valor, motivo))
            continue
        na_lista.setdefault(limpar(item.valor), []).append(item.local)

    nos_arquivos: dict[str, list[Path]] = {}
    for arquivo in listar_xmls(base, recursivo):
        try:
            nota = ler_nota(arquivo)
        except (NotaInvalidaError, OSError) as erro:
            resultado.invalidas.append(Invalida("xml", str(arquivo), "", _motivo(erro, arquivo)))
            continue
        if not nota.chave_valida:
            motivo = motivo_invalidez(nota.chave) or "invalid access key"
            resultado.invalidas.append(Invalida("xml", str(arquivo), nota.chave, motivo))
            continue
        nos_arquivos.setdefault(nota.chave, []).append(arquivo)

    resultado.esperadas = len(na_lista)
    resultado.encontradas = sum(1 for chave in na_lista if chave in nos_arquivos)
    resultado.faltando = [chave for chave in na_lista if chave not in nos_arquivos]
    resultado.sobrando = [
        Sobra(chave, arquivos[0])
        for chave, arquivos in nos_arquivos.items()
        if chave not in na_lista
    ]
    resultado.duplicadas = [
        Duplicada(chave, "xml", tuple(str(a) for a in arquivos))
        for chave, arquivos in nos_arquivos.items()
        if len(arquivos) > 1
    ] + [
        Duplicada(chave, "list", tuple(locais))
        for chave, locais in na_lista.items()
        if len(locais) > 1
    ]
    return resultado


def para_json(resultado: Conciliacao) -> str:
    return json.dumps(resultado.as_dict(), indent=2, ensure_ascii=False)


def escrever_csv(resultado: Conciliacao, saida: TextIO) -> None:
    """Write one row per finding: ``status,key,location,detail``."""
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(["status", "key", "location", "detail"])
    for chave in resultado.faltando:
        escritor.writerow(["missing", chave, "", ""])
    for sobra in resultado.sobrando:
        escritor.writerow(["extra", sobra.chave, str(sobra.arquivo), ""])
    for dup in resultado.duplicadas:
        escritor.writerow(["duplicate", dup.chave, " | ".join(dup.locais), f"in {dup.origem}"])
    for inv in resultado.invalidas:
        escritor.writerow(["invalid", inv.valor, inv.local, inv.motivo])


def para_csv(resultado: Conciliacao) -> str:
    buffer = io.StringIO()
    escrever_csv(resultado, buffer)
    return buffer.getvalue()


def _ler_texto(caminho: Path) -> str:
    try:
        dados = caminho.read_bytes()
    except OSError as erro:
        raise ListaInvalidaError(
            f"cannot read key list {caminho}: {erro.strerror or erro}"
        ) from None
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("latin-1")


def _ler_csv(texto: str, caminho: Path) -> list[ChaveEsperada]:
    linhas = texto.splitlines()
    if not linhas:
        raise ListaInvalidaError(f"{caminho}: empty CSV file")
    try:
        dialeto = csv.Sniffer().sniff(linhas[0], delimiters=",;\t")
        delimitador = dialeto.delimiter
    except csv.Error:
        delimitador = ","
    leitor = csv.reader(io.StringIO(texto, newline=""), delimiter=delimitador)
    cabecalho = [c.strip().lower() for c in next(leitor)]
    coluna = next((cabecalho.index(n) for n in COLUNAS_CHAVE if n in cabecalho), None)
    if coluna is None:
        raise ListaInvalidaError(
            f"{caminho}: CSV header must have one of these columns: {', '.join(COLUNAS_CHAVE)}"
        )
    itens = []
    for linha in leitor:
        if coluna >= len(linha):
            continue
        valor = linha[coluna].strip().lstrip("'")
        if valor:
            itens.append(ChaveEsperada(valor, f"line {leitor.line_num}"))
    return itens


def _motivo(erro: Exception, arquivo: Path) -> str:
    if isinstance(erro, OSError):
        return f"cannot read file ({erro.strerror or erro})"
    mensagem = str(erro)
    prefixo = f"{arquivo}: "
    return mensagem[len(prefixo) :] if mensagem.startswith(prefixo) else mensagem
