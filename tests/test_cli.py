import io
import json
import subprocess
import sys

import pytest

from fabrica import chave_com_dv_errado, gravar, montar_chave, montar_xml
from nfe_toolkit import __version__
from nfe_toolkit.cli import main

K1 = montar_chave(numero=1)
K2 = montar_chave(numero=2)


def test_validate_ok_e_erro(capsys):
    assert main(["validate", K1]) == 0
    assert f"VALID    {K1}" in capsys.readouterr().out

    ruim = chave_com_dv_errado(K1)
    assert main(["validate", K1, ruim]) == 1
    out = capsys.readouterr().out
    assert f"INVALID  {ruim}" in out and "check digit mismatch" in out


def test_validate_json(capsys):
    assert main(["validate", "--json", "123"]) == 1
    dados = json.loads(capsys.readouterr().out)
    assert dados == [{"key": "123", "valid": False, "reason": "expected 44 digits, got 3"}]


def test_validate_stdin(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{K1}\n\n{K2}\n"))
    assert main(["validate"]) == 0
    assert capsys.readouterr().out.count("VALID") == 2


def test_validate_sem_nada(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["validate"]) == 2
    assert "no access key" in capsys.readouterr().err


def test_info_chave(capsys):
    assert main(["info", K1]) == 0
    out = capsys.readouterr().out
    assert "35 (SP)" in out and "2026-03" in out and "CNPJ 11.222.333/0001-81" in out
    assert "55 (NF-e)" in out


def test_info_chave_json(capsys):
    assert main(["info", "--json", K1]) == 0
    assert json.loads(capsys.readouterr().out)["numero"] == 1


def test_info_chave_invalida(capsys):
    assert main(["info", "123"]) == 1
    assert "invalid access key" in capsys.readouterr().err


def test_info_arquivo(tmp_path, capsys):
    arq = gravar(tmp_path, "n.xml", montar_xml(K1, proc=True))
    assert main(["info", str(arq)]) == 0
    out = capsys.readouterr().out
    assert "11.222.333/0001-81 Empresa Exemplo Ltda" in out
    assert "123.456.789-09 Cliente Exemplo" in out
    assert "150.00" in out and "100 Autorizado" in out
    assert "Year/month" in out


def test_info_arquivo_sem_protocolo_json(tmp_path, capsys):
    arq = gravar(tmp_path, "n.xml", montar_xml(K1, com_dest=False))
    assert main(["info", "--json", str(arq)]) == 0
    dados = json.loads(capsys.readouterr().out)
    assert dados["protocolo_status"] is None
    assert dados["key_fields"]["uf"] == "SP"
    assert main(["info", str(arq)]) == 0
    assert "none (note without authorization protocol)" in capsys.readouterr().out


def test_info_arquivo_com_chave_invalida(tmp_path, capsys):
    arq = gravar(tmp_path, "n.xml", montar_xml(chave_com_dv_errado(K1)))
    assert main(["info", str(arq)]) == 1
    assert "(INVALID)" in capsys.readouterr().out


def test_info_xml_quebrado_sem_stack_trace(tmp_path, capsys):
    arq = gravar(tmp_path, "q.xml", "<NFe><infNFe>")
    assert main(["info", str(arq)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "malformed XML" in err
    assert "Traceback" not in err


def test_info_arquivo_inexistente(tmp_path, capsys):
    assert main(["info", str(tmp_path / "falta.xml")]) == 2
    assert "file not found" in capsys.readouterr().err


def test_organize_dry_run_e_apply(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gravar(tmp_path, "in/a.xml", montar_xml(K1))
    gravar(tmp_path, "in/b-copia.xml", montar_xml(K1))
    gravar(tmp_path, "in/ruim.xml", "nada")

    assert main(["organize", "in", "out"]) == 0
    out = capsys.readouterr().out
    assert "Plan: 1 to move, 1 duplicate(s), 1 unreadable" in out
    assert "move  in/a.xml -> out/2026/03/a.xml" in out
    assert "skip  in/b-copia.xml (same key as in/a.xml)" in out
    assert "Dry run" in out
    assert not (tmp_path / "out").exists()

    assert main(["organize", "in", "out", "--copy"]) == 0
    assert "--copy only takes effect" in capsys.readouterr().err

    assert main(["organize", "in", "out", "--aplicar", "--copiar"]) == 0
    assert "1 file(s) copied" in capsys.readouterr().out
    assert (tmp_path / "in/a.xml").exists()

    assert main(["organize", "in", "out2", "--apply"]) == 0
    assert "1 file(s) moved" in capsys.readouterr().out
    assert (tmp_path / "out2/2026/03/a.xml").exists()
    assert not (tmp_path / "in/a.xml").exists()


def test_organize_apply_com_erro(tmp_path, capsys, monkeypatch):
    import nfe_toolkit.organizar as modulo

    gravar(tmp_path, "in/a.xml", montar_xml(K1))

    def falhar(origem, destino):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(modulo, "_copiar_sem_sobrescrever", falhar)
    assert main(["organize", str(tmp_path / "in"), str(tmp_path / "out"), "--apply"]) == 1
    assert "error" in capsys.readouterr().err


def test_organize_origem_inexistente(tmp_path, capsys):
    assert main(["organize", str(tmp_path / "x"), str(tmp_path / "y")]) == 2
    assert "source folder not found" in capsys.readouterr().err


@pytest.fixture
def caso_reconcile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gravar(tmp_path, "xmls/1.xml", montar_xml(K1))
    gravar(tmp_path, "xmls/extra.xml", montar_xml(montar_chave(numero=9)))
    gravar(tmp_path, "lista.txt", f"{K1}\n{K2}\n")
    gravar(tmp_path, "ok.txt", f"{K1}\n")
    return tmp_path


def test_reconcile_tabela(caso_reconcile, capsys):
    assert main(["reconcile", "xmls", "lista.txt"]) == 1
    out = capsys.readouterr().out
    assert "missing      1" in out and "MISSING (1)" in out and K2 in out
    assert "EXTRA, not in the list (1)" in out and "xmls/extra.xml" in out
    assert out.rstrip().endswith("FAILED: missing keys.")


def test_reconcile_ok_e_strict(caso_reconcile, capsys):
    assert main(["reconcile", "xmls", "ok.txt"]) == 0
    assert "OK: every expected key was found." in capsys.readouterr().out
    assert main(["reconcile", "xmls", "ok.txt", "--strict"]) == 1


def test_reconcile_json_csv_e_output(caso_reconcile, capsys):
    assert main(["reconcile", "xmls", "lista.txt", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["missing"] == [K2]

    assert main(["reconcile", "xmls", "lista.txt", "--csv", "-o", "rel.csv"]) == 1
    assert "report written to rel.csv" in capsys.readouterr().err
    texto = (caso_reconcile / "rel.csv").read_text(encoding="utf-8")
    assert texto.startswith("status,key,location,detail\n")
    assert f"missing,{K2}" in texto


def test_reconcile_lista_inexistente(caso_reconcile, capsys):
    assert main(["reconcile", "xmls", "nao-existe.txt"]) == 2
    assert "cannot read key list" in capsys.readouterr().err


def test_reconcile_mostra_duplicadas_e_invalidas(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gravar(tmp_path, "x/a.xml", montar_xml(K1))
    gravar(tmp_path, "x/b.xml", montar_xml(K1))
    gravar(tmp_path, "x/q.xml", "<a>")
    gravar(tmp_path, "l.txt", f"{K1}\n{K1}\n999\n")
    assert main(["reconcile", "x", "l.txt"]) == 0
    out = capsys.readouterr().out
    assert f"{K1}  xml: x/a.xml, x/b.xml" in out
    assert f"{K1}  list: line 1, line 2" in out
    assert "list line 3: 999  expected 44 digits, got 3" in out
    assert "x/q.xml: malformed XML" in out


def test_erro_oserror_generico(tmp_path, capsys, monkeypatch):
    import nfe_toolkit.cli as cli

    def falhar(*_args, **_kw):
        raise PermissionError(13, "Permission denied", "segredo.xml")

    monkeypatch.setattr(cli, "conciliar", falhar)
    assert main(["reconcile", str(tmp_path), "l.txt"]) == 2
    assert capsys.readouterr().err.strip() == "error: Permission denied: segredo.xml"


def test_interrompido(capsys, monkeypatch):
    import nfe_toolkit.cli as cli

    def parar(*_a, **_k):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "motivo_invalidez", parar)
    assert main(["validate", K1]) == 130


def test_version(capsys):
    with pytest.raises(SystemExit) as saida:
        main(["--version"])
    assert saida.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_sem_subcomando(capsys):
    with pytest.raises(SystemExit) as saida:
        main([])
    assert saida.value.code == 2


def test_python_m(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "nfe_toolkit", "validate", K1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "VALID" in proc.stdout
