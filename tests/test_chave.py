import pytest

from fabrica import CNPJ_EXEMPLO, CPF_EXEMPLO, chave_com_dv_errado, montar_chave
from nfe_toolkit import chave as ch
from nfe_toolkit.erros import ChaveInvalidaError

# Worked example: 43 digits whose weighted sum is checked by hand below.
BASE = "3526031122233300018155001000001234112345678"


def test_calcular_dv_soma_ponderada_manual():
    soma = 0
    peso = 2
    for d in reversed(BASE):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    esperado = 0 if resto < 2 else 11 - resto
    assert ch.calcular_dv(BASE) == esperado


@pytest.mark.parametrize("numero", range(1, 60))
def test_dv_sempre_entre_0_e_9(numero):
    chave = montar_chave(numero=numero)
    assert 0 <= int(chave[-1]) <= 9
    assert ch.validar(chave)


def test_dv_zero_quando_resto_menor_que_dois():
    # Find bases whose remainder is 0 or 1 and check that the digit is 0.
    achados = 0
    for numero in range(1, 500):
        base = montar_chave(numero=numero)[:43]
        soma, peso = 0, 2
        for d in reversed(base):
            soma += int(d) * peso
            peso = 2 if peso == 9 else peso + 1
        if soma % 11 < 2:
            assert ch.calcular_dv(base) == 0
            achados += 1
    assert achados > 0


def test_calcular_dv_rejeita_tamanho_errado():
    with pytest.raises(ChaveInvalidaError):
        ch.calcular_dv("123")
    with pytest.raises(ChaveInvalidaError):
        ch.calcular_dv("a" * 43)
    with pytest.raises(ChaveInvalidaError):
        ch.calcular_dv(None)  # type: ignore[arg-type]


def test_validar_chave_correta_e_formatada():
    chave = montar_chave()
    assert ch.validar(chave)
    assert ch.validar(ch.formatar(chave))
    assert ch.validar("NFe" + chave)
    assert ch.validar(f"  {chave}\n")


@pytest.mark.parametrize(
    ("valor", "trecho"),
    [
        ("", "got 0"),
        ("123", "got 3"),
        ("1" * 45, "got 45"),
        ("A" * 44, "only digits"),
        (chr(0x661) * 44, "only digits"),  # Arabic-Indic digits are not accepted
        (12345, "must be a string"),
        (None, "must be a string"),
    ],
)
def test_motivo_invalidez(valor, trecho):
    motivo = ch.motivo_invalidez(valor)
    assert motivo is not None and trecho in motivo
    assert not ch.validar(valor)


def test_dv_errado():
    chave = chave_com_dv_errado(montar_chave())
    assert not ch.validar(chave)
    assert "check digit mismatch" in ch.motivo_invalidez(chave)


def test_formatar_grupos_de_quatro():
    chave = montar_chave()
    formatada = ch.formatar(chave)
    grupos = formatada.split(" ")
    assert len(grupos) == 11
    assert all(len(g) == 4 for g in grupos)
    assert "".join(grupos) == chave


def test_decompor_nfe_cnpj():
    chave = montar_chave(cuf="35", aamm="2603", modelo="55", serie=1, numero=1234, cnf="12345678")
    info = ch.decompor(chave)
    assert info.cuf == "35" and info.uf == "SP"
    assert (info.ano, info.mes) == (2026, 3)
    assert info.emitente_tipo == "CNPJ"
    assert info.emitente_documento == CNPJ_EXEMPLO
    assert info.emitente_formatado == "11.222.333/0001-81"
    assert info.modelo == "55" and info.modelo_descricao == "NF-e"
    assert info.serie == 1 and info.numero == 1234
    assert info.tp_emis == "1" and info.tp_emis_descricao == "normal"
    assert info.cnf == "12345678"
    assert info.dv == int(chave[-1])
    assert info.as_dict()["uf"] == "SP"


def test_decompor_nfce_cpf_e_contingencia():
    chave = montar_chave(cuf="31", modelo="65", documento="000" + CPF_EXEMPLO, tp_emis="9")
    info = ch.decompor(chave)
    assert info.uf == "MG"
    assert info.modelo_descricao == "NFC-e"
    assert info.emitente_tipo == "CPF"
    assert info.emitente_documento == CPF_EXEMPLO
    assert info.emitente_formatado == "123.456.789-09"
    assert info.tp_emis_descricao == "offline contingency (NFC-e)"


def test_decompor_uf_e_modelo_desconhecidos():
    info = ch.decompor(montar_chave(cuf="99", modelo="99", tp_emis="8"))
    assert info.uf is None
    assert info.modelo_descricao is None
    assert info.tp_emis_descricao is None


def test_decompor_documento_que_nao_e_cnpj_nem_cpf_vira_cnpj():
    info = ch.decompor(montar_chave(documento="12345678901234"))
    assert info.emitente_tipo == "CNPJ"
    assert info.emitente_formatado == "12.345.678/9012-34"


def test_decompor_chave_invalida():
    with pytest.raises(ChaveInvalidaError, match="check digit"):
        ch.decompor(chave_com_dv_errado(montar_chave()))


def test_cnpj_e_cpf_validos():
    assert ch.cnpj_valido(CNPJ_EXEMPLO)
    assert not ch.cnpj_valido("11222333000182")
    assert not ch.cnpj_valido("1" * 14)
    assert not ch.cnpj_valido("123")
    assert ch.cpf_valido(CPF_EXEMPLO)
    assert not ch.cpf_valido("12345678900")
    assert not ch.cpf_valido("12345678919")
    assert not ch.cpf_valido("0" * 11)
