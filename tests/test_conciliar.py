import csv
import io
import json

import pytest

from fabrica import chave_com_dv_errado, gravar, montar_chave, montar_xml
from nfe_toolkit.conciliar import (
    ChaveEsperada,
    conciliar,
    conciliar_chaves,
    ler_lista,
    para_csv,
    para_json,
)
from nfe_toolkit.erros import ListaInvalidaError, NfeToolkitError

K1 = montar_chave(numero=1)
K2 = montar_chave(numero=2)
K3 = montar_chave(numero=3)
K4 = montar_chave(numero=4)


@pytest.fixture
def pasta(tmp_path):
    p = tmp_path / "xmls"
    gravar(p, "1.xml", montar_xml(K1, proc=True))
    gravar(p, "2.xml", montar_xml(K2))
    gravar(p, "sub/2-copia.xml", montar_xml(K2))
    gravar(p, "4.xml", montar_xml(K4))
    gravar(p, "quebrado.xml", "<nfeProc>")
    gravar(p, "dv.xml", montar_xml(chave_com_dv_errado(montar_chave(numero=5))))
    return p


def test_conciliacao_completa(pasta, tmp_path):
    lista = gravar(tmp_path, "lista.txt", f"# exported list\n{K1}\n\n{K2}\n{K3}\n123\n{K1}\n")
    r = conciliar(pasta, lista)
    assert r.esperadas == 3
    assert r.encontradas == 2
    assert r.faltando == [K3]
    assert [(s.chave, s.arquivo.name) for s in r.sobrando] == [(K4, "4.xml")]
    dups = {(d.chave, d.origem): d.locais for d in r.duplicadas}
    assert len(dups[(K2, "xml")]) == 2
    assert dups[(K1, "list")] == ("line 2", "line 7")
    invalidas = {(i.origem, i.local.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]) for i in r.invalidas}
    assert ("list", "line 6") in invalidas
    assert ("xml", "quebrado.xml") in invalidas
    assert ("xml", "dv.xml") in invalidas
    assert not r.ok and not r.limpa


def test_tudo_certo(pasta):
    r = conciliar_chaves(pasta, [K1, K2, K4])
    assert r.ok
    assert r.faltando == []
    assert not r.limpa  # duplicates and broken files are still reported


def test_pasta_limpa(tmp_path):
    p = tmp_path / "ok"
    gravar(p, "1.xml", montar_xml(K1))
    r = conciliar_chaves(p, [ChaveEsperada(K1, "line 1")])
    assert r.ok and r.limpa


def test_lista_csv_ponto_e_virgula_com_bom(tmp_path):
    texto = f"﻿numero;Chave;valor\n1;{K1};10,00\n2;'{K2};20,00\n3;;0\n4\n"
    lista = gravar(tmp_path, "lista.csv", texto)
    itens = ler_lista(lista)
    assert [i.valor for i in itens] == [K1, K2]
    assert itens[0].local == "line 2"


def test_lista_csv_virgula_coluna_key(tmp_path):
    lista = gravar(tmp_path, "l.csv", f"key,obs\n{K1},a\n")
    assert [i.valor for i in ler_lista(lista)] == [K1]


def test_lista_csv_latin1(tmp_path):
    lista = tmp_path / "l.csv"
    lista.write_bytes(f"chave;descrição\n{K1};ação\n".encode("latin-1"))
    assert [i.valor for i in ler_lista(lista)] == [K1]


def test_lista_csv_sem_coluna(tmp_path):
    lista = gravar(tmp_path, "l.csv", "numero;valor\n1;2\n")
    with pytest.raises(ListaInvalidaError, match="header"):
        ler_lista(lista)


def test_lista_csv_vazia(tmp_path):
    with pytest.raises(ListaInvalidaError, match="empty"):
        ler_lista(gravar(tmp_path, "l.csv", ""))


def test_lista_inexistente(tmp_path):
    with pytest.raises(ListaInvalidaError, match="cannot read"):
        ler_lista(tmp_path / "nao-existe.txt")


def test_pasta_inexistente(tmp_path):
    with pytest.raises(NfeToolkitError, match="folder not found"):
        conciliar_chaves(tmp_path / "nada", [K1])


def test_saida_json_e_csv(pasta):
    r = conciliar_chaves(pasta, [K1, K3])
    dados = json.loads(para_json(r))
    assert dados["summary"]["missing"] == 1
    assert dados["missing"] == [K3]
    assert dados["extra"][0]["key"] in (K2, K4)

    linhas = list(csv.DictReader(io.StringIO(para_csv(r))))
    status = [linha["status"] for linha in linhas]
    assert status.count("missing") == 1
    assert status.count("extra") == 2
    assert "duplicate" in status and "invalid" in status
