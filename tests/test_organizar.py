import pytest

from fabrica import chave_com_dv_errado, gravar, montar_chave, montar_xml
from nfe_toolkit.erros import NfeToolkitError
from nfe_toolkit.organizar import aplicar, planejar


@pytest.fixture
def entrada(tmp_path):
    origem = tmp_path / "entrada"
    gravar(origem, "a.xml", montar_xml(montar_chave(aamm="2603", numero=1)))
    gravar(origem, "sub/b.xml", montar_xml(montar_chave(aamm="2511", numero=2), proc=True))
    gravar(origem, "copia-de-a.xml", montar_xml(montar_chave(aamm="2603", numero=1)))
    gravar(origem, "quebrado.xml", "<NFe><infNFe")
    gravar(origem, "dv-errado.xml", montar_xml(chave_com_dv_errado(montar_chave(numero=3))))
    gravar(origem, "leia-me.txt", "ignorado")
    return origem


def test_plano_nao_toca_em_nada(entrada, tmp_path):
    destino = tmp_path / "organizado"
    antes = sorted(p.relative_to(entrada) for p in entrada.rglob("*"))
    plano = planejar(entrada, destino)
    assert sorted(p.relative_to(entrada) for p in entrada.rglob("*")) == antes
    assert not destino.exists()

    alvos = {m.origem.name: m.destino.relative_to(destino).as_posix() for m in plano.movimentos}
    assert alvos == {"a.xml": "2026/03/a.xml", "b.xml": "2025/11/b.xml"}
    assert [d.arquivo.name for d in plano.duplicados] == ["copia-de-a.xml"]
    assert plano.duplicados[0].original.name == "a.xml"
    falhas = {f.arquivo.name: f.motivo for f in plano.falhas}
    assert set(falhas) == {"quebrado.xml", "dv-errado.xml"}
    assert "malformed XML" in falhas["quebrado.xml"]
    assert "invalid access key" in falhas["dv-errado.xml"]


def test_aplicar_move(entrada, tmp_path):
    destino = tmp_path / "organizado"
    resultado = aplicar(planejar(entrada, destino))
    assert not resultado.falhas
    assert (destino / "2026/03/a.xml").is_file()
    assert (destino / "2025/11/b.xml").is_file()
    assert not (entrada / "a.xml").exists()
    # duplicates and broken files stay where they were
    assert (entrada / "copia-de-a.xml").exists()
    assert (entrada / "quebrado.xml").exists()


def test_aplicar_copia(entrada, tmp_path):
    destino = tmp_path / "organizado"
    resultado = aplicar(planejar(entrada, destino), copiar=True)
    assert len(resultado.feitos) == 2
    assert (destino / "2026/03/a.xml").is_file()
    assert (entrada / "a.xml").is_file()


def test_nunca_sobrescreve_nome_repetido(tmp_path):
    origem = tmp_path / "in"
    destino = tmp_path / "out"
    gravar(origem, "x/nota.xml", montar_xml(montar_chave(numero=10)))
    gravar(origem, "y/nota.xml", montar_xml(montar_chave(numero=11)))
    existente = gravar(destino, "2026/03/nota.xml", "conteudo antigo, nao e nota")
    plano = planejar(origem, destino)
    nomes = sorted(m.destino.name for m in plano.movimentos)
    assert nomes == ["nota_2.xml", "nota_3.xml"]
    aplicar(plano)
    assert existente.read_text(encoding="utf-8") == "conteudo antigo, nao e nota"
    assert (destino / "2026/03/nota_2.xml").is_file()
    assert (destino / "2026/03/nota_3.xml").is_file()


def test_arquivo_criado_entre_plano_e_aplicacao(tmp_path):
    origem = tmp_path / "in"
    destino = tmp_path / "out"
    gravar(origem, "nota.xml", montar_xml())
    plano = planejar(origem, destino)
    intruso = gravar(destino, "2026/03/nota.xml", "apareceu depois")
    resultado = aplicar(plano)
    assert intruso.read_text(encoding="utf-8") == "apareceu depois"
    assert resultado.feitos[0].destino.name == "nota_2.xml"


def test_duplicado_contra_pasta_ja_organizada(tmp_path):
    origem = tmp_path / "in"
    destino = tmp_path / "out"
    chave = montar_chave(numero=50)
    gravar(destino, "2026/03/original.xml", montar_xml(chave))
    gravar(destino, "2026/03/lixo.xml", "nao e xml")
    gravar(origem, "de-novo.xml", montar_xml(chave))
    plano = planejar(origem, destino)
    assert not plano.movimentos
    assert plano.duplicados[0].original.name == "original.xml"


def test_destino_dentro_da_origem_e_rodar_duas_vezes(tmp_path):
    pasta = tmp_path / "xmls"
    gravar(pasta, "a.xml", montar_xml(montar_chave(numero=1)))
    gravar(pasta, "b.xml", montar_xml(montar_chave(numero=2, aamm="2601")))
    aplicar(planejar(pasta, pasta))
    assert (pasta / "2026/03/a.xml").is_file()
    assert (pasta / "2026/01/b.xml").is_file()
    segundo = planejar(pasta, pasta)
    assert not segundo.movimentos and not segundo.duplicados and not segundo.falhas


def test_nao_recursivo(entrada, tmp_path):
    plano = planejar(entrada, tmp_path / "out", recursivo=False)
    assert "b.xml" not in {m.origem.name for m in plano.movimentos}


def test_erros_de_pasta(tmp_path):
    with pytest.raises(NfeToolkitError, match="source folder not found"):
        planejar(tmp_path / "nao-existe", tmp_path / "out")
    arquivo = gravar(tmp_path, "arquivo.txt", "x")
    (tmp_path / "in").mkdir()
    with pytest.raises(NfeToolkitError, match="not a folder"):
        planejar(tmp_path / "in", arquivo)


def test_falha_de_io_na_aplicacao_nao_para_o_lote(entrada, tmp_path):
    plano = planejar(entrada, tmp_path / "out")
    plano.movimentos[0].origem.unlink()  # file vanished after planning
    resultado = aplicar(plano)
    assert len(resultado.falhas) == 1
    assert len(resultado.feitos) == 1


def test_arquivo_ilegivel_no_plano(tmp_path, monkeypatch):
    import nfe_toolkit.organizar as modulo

    origem = tmp_path / "in"
    gravar(origem, "a.xml", montar_xml())

    def falhar(_):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(modulo, "ler_nota", falhar)
    plano = planejar(origem, tmp_path / "out")
    assert "cannot read file" in plano.falhas[0].motivo
