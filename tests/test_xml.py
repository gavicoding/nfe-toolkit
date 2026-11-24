from decimal import Decimal

import pytest

from fabrica import CNPJ_EXEMPLO, chave_com_dv_errado, gravar, montar_chave, montar_xml
from nfe_toolkit.erros import NotaInvalidaError
from nfe_toolkit.xml import ler_nota, ler_nota_bytes, listar_xmls


def test_nfe_pura_sem_protocolo(tmp_path):
    chave = montar_chave()
    arq = gravar(tmp_path, "nota.xml", montar_xml(chave))
    nota = ler_nota(arq)
    assert nota.arquivo == arq
    assert nota.chave == chave and nota.chave_valida
    assert nota.modelo == "55"
    assert nota.serie == 1 and nota.numero == 1234
    assert nota.data_emissao == "2026-03-10T09:15:00-03:00"
    assert nota.emitente_documento == CNPJ_EXEMPLO
    assert nota.emitente_nome == "Empresa Exemplo Ltda"
    assert nota.destinatario_documento == "12345678909"
    assert nota.destinatario_nome == "Cliente Exemplo"
    assert nota.valor_total == Decimal("150.00")
    assert nota.protocolo_status is None
    assert not nota.tem_protocolo and not nota.autorizada


def test_nfeproc_com_protocolo(tmp_path):
    chave = montar_chave(numero=77)
    arq = gravar(tmp_path, "proc.xml", montar_xml(chave, proc=True))
    nota = ler_nota(arq)
    assert nota.chave == chave
    assert nota.protocolo_status == "100"
    assert nota.protocolo_numero == "135260000000001"
    assert nota.protocolo_motivo.startswith("Autorizado")
    assert nota.autorizada
    dados = nota.as_dict()
    assert dados["valor_total"] == "150.00"
    assert dados["arquivo"] == str(arq)
    assert dados["autorizada"] is True


def test_protocolo_rejeitado_nao_e_autorizada():
    nota = ler_nota_bytes(montar_xml(proc=True, status="302").encode())
    assert nota.tem_protocolo and not nota.autorizada


def test_nfce_sem_destinatario_e_sem_namespace():
    chave = montar_chave(modelo="65", numero=5)
    nota = ler_nota_bytes(montar_xml(chave, namespace=False, com_dest=False).encode())
    assert nota.modelo == "65"
    assert nota.destinatario_documento is None
    assert nota.destinatario_nome is None
    assert nota.arquivo is None


def test_chave_vinda_do_protocolo_quando_falta_id():
    chave = montar_chave(numero=9)
    nota = ler_nota_bytes(montar_xml(chave, proc=True, id_no_infnfe=False).encode())
    assert nota.chave == chave


def test_sem_chave_nenhuma():
    with pytest.raises(NotaInvalidaError, match="access key not found"):
        ler_nota_bytes(montar_xml(id_no_infnfe=False).encode())


def test_chave_com_dv_errado_e_lida_mas_marcada():
    chave = chave_com_dv_errado(montar_chave())
    nota = ler_nota_bytes(montar_xml(chave).encode())
    assert nota.chave == chave
    assert not nota.chave_valida


def test_modelo_vem_da_chave_quando_falta_mod():
    chave = montar_chave(modelo="65")
    xml = montar_xml(chave).replace("<mod>65</mod>", "")
    assert ler_nota_bytes(xml.encode()).modelo == "65"


def test_campos_numericos_estranhos_viram_none():
    xml = montar_xml().replace("<vNF>150.00</vNF>", "<vNF>abc</vNF>")
    xml = xml.replace("<serie>1</serie>", "<serie>x</serie>")
    nota = ler_nota_bytes(xml.encode())
    assert nota.valor_total is None
    assert nota.serie is None
    nan = montar_xml().replace("<vNF>150.00</vNF>", "<vNF>NaN</vNF>")
    assert ler_nota_bytes(nan.encode()).valor_total is None


def test_data_antiga_demi():
    xml = montar_xml().replace(
        "<dhEmi>2026-03-10T09:15:00-03:00</dhEmi>", "<dEmi>2009-05-01</dEmi>"
    )
    assert ler_nota_bytes(xml.encode()).data_emissao == "2009-05-01"


def test_xml_malformado(tmp_path):
    arq = gravar(tmp_path, "quebrado.xml", montar_xml()[:-20])
    with pytest.raises(NotaInvalidaError, match="malformed XML"):
        ler_nota(arq)


def test_xml_que_nao_e_nfe():
    with pytest.raises(NotaInvalidaError, match="no infNFe"):
        ler_nota_bytes(b"<root><a>1</a></root>")


def test_dtd_e_entidades_recusados():
    xml = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(NotaInvalidaError, match="not allowed"):
        ler_nota_bytes(xml)


def test_arquivo_inexistente(tmp_path):
    with pytest.raises(OSError):
        ler_nota(tmp_path / "nao-existe.xml")


def test_arquivo_grande_demais(tmp_path, monkeypatch):
    import nfe_toolkit.xml as modulo

    monkeypatch.setattr(modulo, "TAMANHO_MAXIMO", 10)
    arq = gravar(tmp_path, "nota.xml", montar_xml())
    with pytest.raises(NotaInvalidaError, match="too large"):
        ler_nota(arq)


def test_listar_xmls(tmp_path):
    gravar(tmp_path, "b.xml", "x")
    gravar(tmp_path, "A.XML", "x")
    gravar(tmp_path, "sub/c.xml", "x")
    gravar(tmp_path, "leia.txt", "x")
    (tmp_path / "pasta.xml").mkdir()
    gravar(tmp_path, "a/z.xml", "x")
    nomes = [p.name for p in listar_xmls(tmp_path)]
    # top-level files first, then subfolders, case-insensitive on every OS
    assert nomes == ["A.XML", "b.xml", "z.xml", "c.xml"]
    assert sorted(p.name for p in listar_xmls(tmp_path, recursivo=False)) == ["A.XML", "b.xml"]
