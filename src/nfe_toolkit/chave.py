"""Access key (chave de acesso) helpers for NF-e and NFC-e.

Layout of the 44 digits::

    cUF(2) AAMM(4) CNPJ/CPF(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) cDV(1)

The check digit is a modulo 11 over the first 43 digits, with weights 2..9
applied from right to left. Remainders 0 and 1 give check digit 0.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .erros import ChaveInvalidaError

UFS: dict[str, str] = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}

MODELOS: dict[str, str] = {"55": "NF-e", "65": "NFC-e"}

TIPOS_EMISSAO: dict[str, str] = {
    "1": "normal",
    "2": "contingency FS-IA",
    "3": "special regime NFF (formerly SCAN)",
    "4": "contingency EPEC",
    "5": "contingency FS-DA",
    "6": "contingency SVC-AN",
    "7": "contingency SVC-RS",
    "9": "offline contingency (NFC-e)",
}

_SEPARADORES = re.compile(r"[\s.\-/]")
_DIGITOS_43 = re.compile(r"[0-9]{43}")
_DIGITOS_44 = re.compile(r"[0-9]{44}")


@dataclass(frozen=True)
class ChaveInfo:
    """Fields encoded in an access key."""

    chave: str
    cuf: str
    uf: str | None
    ano: int
    mes: int
    emitente_tipo: str
    emitente_documento: str
    emitente_formatado: str
    modelo: str
    modelo_descricao: str | None
    serie: int
    numero: int
    tp_emis: str
    tp_emis_descricao: str | None
    cnf: str
    dv: int

    def as_dict(self) -> dict:
        return asdict(self)


def limpar(chave: str) -> str:
    """Remove spaces, dots, dashes, slashes and a leading ``NFe`` prefix."""
    texto = _SEPARADORES.sub("", chave)
    if texto[:3].upper() == "NFE":
        texto = texto[3:]
    return texto


def calcular_dv(chave43: str) -> int:
    """Return the check digit for the first 43 digits of an access key."""
    if not isinstance(chave43, str):
        raise ChaveInvalidaError("access key must be a string")
    texto = limpar(chave43)
    if not _DIGITOS_43.fullmatch(texto):
        raise ChaveInvalidaError(f"expected 43 digits to compute the check digit, got {texto!r}")
    soma = 0
    peso = 2
    for digito in reversed(texto):
        soma += int(digito) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def motivo_invalidez(chave: object) -> str | None:
    """Explain why a key is invalid, or return ``None`` when it is valid."""
    if not isinstance(chave, str):
        return "access key must be a string"
    texto = limpar(chave)
    if len(texto) != 44:
        return f"expected 44 digits, got {len(texto)}"
    if not _DIGITOS_44.fullmatch(texto):
        return "access key must contain only digits"
    esperado = calcular_dv(texto[:43])
    if int(texto[43]) != esperado:
        return f"check digit mismatch (expected {esperado}, got {texto[43]})"
    return None


def validar(chave: object) -> bool:
    """Return ``True`` when ``chave`` has 44 digits and a correct check digit."""
    return motivo_invalidez(chave) is None


def formatar(chave: str) -> str:
    """Format a key in groups of 4 digits, as printed on the DANFE."""
    texto = limpar(chave)
    return " ".join(texto[i : i + 4] for i in range(0, len(texto), 4))


def decompor(chave: str) -> ChaveInfo:
    """Split a valid key into its fields. Raises ``ChaveInvalidaError`` otherwise."""
    motivo = motivo_invalidez(chave)
    if motivo:
        raise ChaveInvalidaError(f"invalid access key: {motivo}")
    texto = limpar(chave)
    documento = texto[6:20]
    tipo, formatado = _identificar_emitente(documento)
    cuf = texto[0:2]
    modelo = texto[20:22]
    tp_emis = texto[34]
    return ChaveInfo(
        chave=texto,
        cuf=cuf,
        uf=UFS.get(cuf),
        ano=2000 + int(texto[2:4]),
        mes=int(texto[4:6]),
        emitente_tipo=tipo,
        emitente_documento=documento if tipo == "CNPJ" else documento[3:],
        emitente_formatado=formatado,
        modelo=modelo,
        modelo_descricao=MODELOS.get(modelo),
        serie=int(texto[22:25]),
        numero=int(texto[25:34]),
        tp_emis=tp_emis,
        tp_emis_descricao=TIPOS_EMISSAO.get(tp_emis),
        cnf=texto[35:43],
        dv=int(texto[43]),
    )


def formatar_cnpj(cnpj: str) -> str:
    return f"{cnpj[0:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"


def formatar_cpf(cpf: str) -> str:
    return f"{cpf[0:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:11]}"


def cnpj_valido(cnpj: str) -> bool:
    if not re.fullmatch(r"[0-9]{14}", cnpj) or len(set(cnpj)) == 1:
        return False

    def dv(base: str, pesos: list[int]) -> int:
        resto = sum(int(d) * p for d, p in zip(base, pesos, strict=True)) % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(cnpj[:12], pesos1)
    d2 = dv(cnpj[:12] + str(d1), [6, *pesos1])
    return cnpj[12:] == f"{d1}{d2}"


def cpf_valido(cpf: str) -> bool:
    if not re.fullmatch(r"[0-9]{11}", cpf) or len(set(cpf)) == 1:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if (soma * 10 % 11) % 10 != int(cpf[tamanho]):
            return False
    return True


def _identificar_emitente(documento: str) -> tuple[str, str]:
    """Tell a CNPJ from a CPF stored in the 14-digit issuer field.

    A CPF issuer is stored with three leading zeros. When the field is a valid
    CNPJ it is treated as one; otherwise a valid CPF after ``000`` wins.
    """
    if cnpj_valido(documento):
        return "CNPJ", formatar_cnpj(documento)
    if documento.startswith("000") and cpf_valido(documento[3:]):
        return "CPF", formatar_cpf(documento[3:])
    return "CNPJ", formatar_cnpj(documento)
