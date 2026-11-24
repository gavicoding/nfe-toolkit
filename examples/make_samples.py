"""Generate the fictitious sample files used in the README.

    python examples/make_samples.py

Writes ``examples/inbox/`` (XML files) and ``examples/expected-keys.txt``.
Every company, document and value here is made up.
"""

from __future__ import annotations

from pathlib import Path

from nfe_toolkit.chave import calcular_dv

AQUI = Path(__file__).resolve().parent
CNPJ = "11222333000181"  # example CNPJ, not a real company


def chave(aamm: str, modelo: str, numero: int, cuf: str = "35", serie: int = 1) -> str:
    base = f"{cuf}{aamm}{CNPJ}{modelo}{serie:03d}{numero:09d}1{numero:08d}"
    return base + str(calcular_dv(base))


def nota(k: str, valor: str, data: str, proc: bool, dest: bool = True) -> str:
    dest_xml = "<dest><CPF>12345678909</CPF><xNome>Cliente Exemplo</xNome></dest>" if dest else ""
    nfe = (
        '<NFe xmlns="http://www.portalfiscal.inf.br/nfe">'
        f'<infNFe versao="4.00" Id="NFe{k}">'
        f"<ide><cUF>{k[:2]}</cUF><mod>{k[20:22]}</mod><serie>{int(k[22:25])}</serie>"
        f"<nNF>{int(k[25:34])}</nNF><dhEmi>{data}</dhEmi></ide>"
        f"<emit><CNPJ>{CNPJ}</CNPJ><xNome>Empresa Exemplo Ltda</xNome></emit>{dest_xml}"
        f"<total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total>"
        "</infNFe></NFe>"
    )
    if not proc:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + nfe + "\n"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
        f'{nfe}<protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><chNFe>{k}</chNFe>'
        f"<dhRecbto>{data}</dhRecbto><nProt>135260000{int(k[25:34]):06d}</nProt>"
        "<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>"
        "</nfeProc>\n"
    )


def main() -> None:
    inbox = AQUI / "inbox"
    (inbox / "downloads").mkdir(parents=True, exist_ok=True)

    k1 = chave("2603", "55", 1201)
    k2 = chave("2603", "55", 1202)
    k3 = chave("2604", "65", 88, serie=2)
    k4 = chave("2511", "55", 990)
    k_missing = chave("2604", "55", 1305)

    (inbox / f"{k1}-procNFe.xml").write_text(
        nota(k1, "1520.40", "2026-03-02T10:12:00-03:00", True), encoding="utf-8"
    )
    (inbox / "NF-1202.xml").write_text(
        nota(k2, "89.90", "2026-03-15T16:40:00-03:00", False), encoding="utf-8"
    )
    (inbox / "downloads" / "cupom-0088.xml").write_text(
        nota(k3, "37.50", "2026-04-01T08:05:00-03:00", True, dest=False), encoding="utf-8"
    )
    (inbox / "downloads" / "NF-1202 (1).xml").write_text(
        nota(k2, "89.90", "2026-03-15T16:40:00-03:00", False), encoding="utf-8"
    )
    (inbox / "nota-antiga.xml").write_text(
        nota(k4, "410.00", "2025-11-20T11:00:00-03:00", True), encoding="utf-8"
    )
    (inbox / "corrompido.xml").write_text(
        '<?xml version="1.0"?>\n<nfeProc><NFe><infNFe Id="NFe', encoding="utf-8"
    )

    (AQUI / "expected-keys.txt").write_text(
        "# keys exported from the accounting system\n"
        f"{k1}\n{k2}\n{k3}\n{k_missing}\n3526031122233300018155001\n",
        encoding="utf-8",
    )
    print(f"samples written to {inbox}")


if __name__ == "__main__":
    main()
