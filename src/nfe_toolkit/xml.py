"""Read NF-e/NFC-e XML files without caring about namespaces.

Accepts a bare ``<NFe>`` document, a ``<nfeProc>`` (note + authorization
protocol) and other envelopes, as long as an ``infNFe`` element is present.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import chave as _chave
from .erros import NotaInvalidaError

#: XML files larger than this are rejected (an NF-e is usually a few KB).
TAMANHO_MAXIMO = 20 * 1024 * 1024

#: Protocol status codes that mean "authorized".
STATUS_AUTORIZADA = {"100", "150"}


@dataclass(frozen=True)
class Nota:
    """Summary of one NF-e/NFC-e."""

    arquivo: Path | None
    chave: str
    chave_valida: bool
    modelo: str | None
    serie: int | None
    numero: int | None
    data_emissao: str | None
    emitente_documento: str | None
    emitente_nome: str | None
    destinatario_documento: str | None
    destinatario_nome: str | None
    valor_total: Decimal | None
    protocolo_status: str | None
    protocolo_motivo: str | None
    protocolo_numero: str | None

    @property
    def tem_protocolo(self) -> bool:
        return self.protocolo_status is not None

    @property
    def autorizada(self) -> bool:
        return self.protocolo_status in STATUS_AUTORIZADA

    def as_dict(self) -> dict:
        dados = {}
        for campo in fields(self):
            valor = getattr(self, campo.name)
            if isinstance(valor, (Path, Decimal)):
                valor = str(valor)
            dados[campo.name] = valor
        dados["autorizada"] = self.autorizada
        return dados


def ler_nota(path: str | Path) -> Nota:
    """Read an XML file and return a :class:`Nota`.

    Raises :class:`NotaInvalidaError` for malformed XML or documents that are
    not an NF-e/NFC-e, and ``OSError`` when the file cannot be read.
    """
    caminho = Path(path)
    tamanho = caminho.stat().st_size
    if tamanho > TAMANHO_MAXIMO:
        raise NotaInvalidaError(f"{caminho}: file too large ({tamanho} bytes)")
    return ler_nota_bytes(caminho.read_bytes(), arquivo=caminho)


def ler_nota_bytes(dados: bytes, arquivo: Path | None = None) -> Nota:
    """Parse XML content already loaded in memory."""
    nome = str(arquivo) if arquivo else "<memory>"
    if b"<!DOCTYPE" in dados or b"<!ENTITY" in dados:
        raise NotaInvalidaError(f"{nome}: DTD and entity declarations are not allowed")
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError as erro:
        raise NotaInvalidaError(f"{nome}: malformed XML ({erro})") from None

    inf = _primeiro(raiz, "infNFe")
    if inf is None:
        raise NotaInvalidaError(f"{nome}: not an NF-e/NFC-e document (no infNFe element)")
    inf_prot = _primeiro(raiz, "infProt")

    chave = _chave_do_documento(inf, inf_prot)
    if not chave:
        raise NotaInvalidaError(f"{nome}: access key not found (infNFe/@Id or chNFe)")

    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    dest = _filho(inf, "dest")
    icms_tot = _filho(_filho(inf, "total"), "ICMSTot")

    modelo = _texto(ide, "mod")
    if modelo is None and len(chave) == 44:
        modelo = chave[20:22]

    return Nota(
        arquivo=arquivo,
        chave=chave,
        chave_valida=_chave.validar(chave),
        modelo=modelo,
        serie=_inteiro(_texto(ide, "serie")),
        numero=_inteiro(_texto(ide, "nNF")),
        data_emissao=_texto(ide, "dhEmi") or _texto(ide, "dEmi"),
        emitente_documento=_texto(emit, "CNPJ") or _texto(emit, "CPF"),
        emitente_nome=_texto(emit, "xNome"),
        destinatario_documento=(
            _texto(dest, "CNPJ") or _texto(dest, "CPF") or _texto(dest, "idEstrangeiro")
        ),
        destinatario_nome=_texto(dest, "xNome"),
        valor_total=_decimal(_texto(icms_tot, "vNF")),
        protocolo_status=_texto(inf_prot, "cStat"),
        protocolo_motivo=_texto(inf_prot, "xMotivo"),
        protocolo_numero=_texto(inf_prot, "nProt"),
    )


def listar_xmls(pasta: str | Path, recursivo: bool = True) -> Iterator[Path]:
    """Yield ``*.xml`` files (any letter case) under ``pasta``.

    The order is the same on every OS: files closer to ``pasta`` come first,
    then case-insensitive path order. The first file seen for a key is the
    one kept as "original" when duplicates are found.
    """
    base = Path(pasta)
    candidatos = base.rglob("*") if recursivo else base.glob("*")
    arquivos = [p for p in candidatos if p.suffix.lower() == ".xml" and p.is_file()]

    def ordem(p: Path) -> tuple[int, str, str]:
        relativo = p.relative_to(base)
        return (len(relativo.parts), relativo.as_posix().lower(), relativo.as_posix())

    yield from sorted(arquivos, key=ordem)


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _primeiro(elemento: ET.Element, nome: str) -> ET.Element | None:
    for item in elemento.iter():
        if _local(item.tag) == nome:
            return item
    return None


def _filho(elemento: ET.Element | None, nome: str) -> ET.Element | None:
    if elemento is None:
        return None
    for item in elemento:
        if _local(item.tag) == nome:
            return item
    return None


def _texto(elemento: ET.Element | None, nome: str) -> str | None:
    filho = _filho(elemento, nome)
    if filho is None or filho.text is None:
        return None
    texto = filho.text.strip()
    return texto or None


def _chave_do_documento(inf: ET.Element, inf_prot: ET.Element | None) -> str | None:
    ident = (inf.get("Id") or "").strip()
    if ident:
        return _chave.limpar(ident)
    ch = _texto(inf_prot, "chNFe")
    return _chave.limpar(ch) if ch else None


def _inteiro(texto: str | None) -> int | None:
    if texto is None or not texto.isdigit():
        return None
    return int(texto)


def _decimal(texto: str | None) -> Decimal | None:
    if texto is None:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor if valor.is_finite() else None
