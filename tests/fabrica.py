"""Builds fictitious NF-e/NFC-e documents for the tests.

Every key produced here has a correct check digit. Names, documents and
values are made up (CNPJ 11.222.333/0001-81 is a well-known example number).
"""

from __future__ import annotations

from pathlib import Path

from nfe_toolkit.chave import calcular_dv

CNPJ_EXEMPLO = "11222333000181"
CPF_EXEMPLO = "12345678909"
NS = "http://www.portalfiscal.inf.br/nfe"


def montar_chave(
    cuf: str = "35",
    aamm: str = "2603",
    documento: str = CNPJ_EXEMPLO,
    modelo: str = "55",
    serie: int = 1,
    numero: int = 1234,
    tp_emis: str = "1",
    cnf: str = "12345678",
) -> str:
    base = f"{cuf}{aamm}{documento.zfill(14)}{modelo}{serie:03d}{numero:09d}{tp_emis}{cnf}"
    assert len(base) == 43, base
    return base + str(calcular_dv(base))


def chave_com_dv_errado(chave: str) -> str:
    dv = int(chave[-1])
    return chave[:-1] + str((dv + 1) % 10)


def montar_xml(
    chave: str | None = None,
    *,
    proc: bool = False,
    namespace: bool = True,
    status: str = "100",
    com_dest: bool = True,
    valor: str = "150.00",
    data: str = "2026-03-10T09:15:00-03:00",
    id_no_infnfe: bool = True,
    emit_nome: str = "Empresa Exemplo Ltda",
) -> str:
    chave = chave or montar_chave()
    modelo = chave[20:22]
    serie = int(chave[22:25])
    numero = int(chave[25:34])
    xmlns = f' xmlns="{NS}"' if namespace else ""
    id_attr = f' Id="NFe{chave}"' if id_no_infnfe else ""
    dest = "<dest><CPF>12345678909</CPF><xNome>Cliente Exemplo</xNome></dest>" if com_dest else ""
    nfe = (
        f"<NFe{xmlns}>"
        f'<infNFe versao="4.00"{id_attr}>'
        f"<ide><cUF>{chave[:2]}</cUF><mod>{modelo}</mod><serie>{serie}</serie>"
        f"<nNF>{numero}</nNF><dhEmi>{data}</dhEmi></ide>"
        f"<emit><CNPJ>{CNPJ_EXEMPLO}</CNPJ><xNome>{emit_nome}</xNome></emit>"
        f"{dest}"
        f"<total><ICMSTot><vNF>{valor}</vNF></ICMSTot></total>"
        "</infNFe></NFe>"
    )
    if not proc:
        return '<?xml version="1.0" encoding="UTF-8"?>' + nfe
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<nfeProc versao="4.00"{xmlns}>{nfe}'
        f'<protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><chNFe>{chave}</chNFe>'
        f"<dhRecbto>{data}</dhRecbto><nProt>135260000000001</nProt>"
        f"<cStat>{status}</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo>"
        "</infProt></protNFe></nfeProc>"
    )


def gravar(pasta: Path, nome: str, conteudo: str) -> Path:
    caminho = pasta / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho
