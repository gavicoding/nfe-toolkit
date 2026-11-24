# nfe-toolkit

[![CI](https://github.com/gavicoding/nfe-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/gavicoding/nfe-toolkit/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20a%203.13-blue)
![Dependências](https://img.shields.io/badge/depend%C3%AAncias-0-brightgreen)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green)](LICENSE)

[English](README.md) | Português

Valida, inspeciona, organiza e concilia XMLs de NF-e e NFC-e pela linha de comando ou como
biblioteca Python. Só usa a biblioteca padrão: não há nada para instalar além do próprio pacote.

## O problema

Quem lida com NF-e e NFC-e (desenvolvedores, contadores, TI) esbarra sempre nas mesmas tarefas:

- Essa chave de acesso de 44 dígitos é válida ou alguém digitou errado?
- De quem é essa nota, e de quando, se só tenho a chave?
- Tem milhares de XMLs soltos numa pasta (ou em dez). Separe por mês.
- Quais deles são duplicados?
- O sistema contábil diz que emitimos estas 3.000 notas. Todos os XMLs estão mesmo aqui?

Normalmente isso é feito na mão ou com planilha. O `nfe-toolkit` resolve cada item com um comando,
e as mesmas funções podem ser usadas como biblioteca.

## Instalação

Requer Python 3.10 ou mais novo.

```bash
pip install git+https://github.com/gavicoding/nfe-toolkit.git
```

Ou a partir de um clone:

```bash
git clone https://github.com/gavicoding/nfe-toolkit.git
cd nfe-toolkit
pip install .
```

Isso instala o comando `nfe-toolkit`. `python -m nfe_toolkit` também funciona.

## Uso

Os exemplos abaixo rodam de dentro da pasta [`examples/`](examples/), que tem alguns XMLs
fictícios e uma lista de chaves (para gerar de novo: `python examples/make_samples.py`). Empresas,
documentos e valores são todos inventados. As mensagens do CLI são em inglês.

### `validate`: conferir chaves de acesso

Confere o tamanho, se só há dígitos e o dígito verificador (módulo 11). Espaços, pontos e o prefixo
`NFe` são ignorados, então dá para colar a chave direto do DANFE. As chaves também podem vir pela
entrada padrão, uma por linha.

```console
$ nfe-toolkit validate 35260311222333000181550010000012011000012012 \
    "3526 0311 2223 3300 0181 5500 1000 0012 0111 0000 1200" 3526031122233300018155
VALID    35260311222333000181550010000012011000012012
INVALID  35260311222333000181550010000012011100001200  (check digit mismatch (expected 9, got 0))
INVALID  3526031122233300018155  (expected 44 digits, got 22)
$ echo $?
1
```

### `info`: o que tem dentro de uma chave ou de um XML

```console
$ nfe-toolkit info 35260311222333000181550010000012011000012012
Access key     3526 0311 2223 3300 0181 5500 1000 0012 0110 0001 2012
State          35 (SP)
Year/month     2026-03
Issuer         CNPJ 11.222.333/0001-81
Model          55 (NF-e)
Series         1
Number         1201
Emission type  1 (normal)
Numeric code   00001201
Check digit    2
```

Com um arquivo, lê o XML (`<NFe>` puro ou `<nfeProc>`, com ou sem namespace) e mostra também
emitente, destinatário, valor total e protocolo de autorização:

```console
$ nfe-toolkit info inbox/35260311222333000181550010000012011000012012-procNFe.xml
File         inbox/35260311222333000181550010000012011000012012-procNFe.xml
Access key   35260311222333000181550010000012011000012012
Issued at    2026-03-02T10:12:00-03:00
Issuer       11.222.333/0001-81 Empresa Exemplo Ltda
Recipient    123.456.789-09 Cliente Exemplo
Total (vNF)  1520.40
Protocol     100 Autorizado o uso da NF-e (nProt 135260000001201)
...
```

XML quebrado vira uma linha de erro com código de saída 2, sem stack trace:

```console
$ nfe-toolkit info inbox/corrompido.xml
error: inbox/corrompido.xml: malformed XML (unclosed token: line 2, column 14)
```

Use `--json` para receber tudo em JSON.

### `organize`: separar os XMLs em `DESTINO/AAAA/MM/`

Ano e mês vêm da chave de acesso. **O padrão é só simular**: o comando mostra o plano e não mexe
em nada.

```console
$ nfe-toolkit organize inbox organized
Plan: 4 to move, 1 duplicate(s), 1 unreadable
  move  inbox/35260311222333000181550010000012011000012012-procNFe.xml -> organized/2026/03/35260311222333000181550010000012011000012012-procNFe.xml
  move  inbox/NF-1202.xml -> organized/2026/03/NF-1202.xml
  move  inbox/nota-antiga.xml -> organized/2025/11/nota-antiga.xml
  move  inbox/downloads/cupom-0088.xml -> organized/2026/04/cupom-0088.xml
  skip  inbox/downloads/NF-1202 (1).xml (same key as inbox/NF-1202.xml)
  fail  inbox/corrompido.xml: malformed XML (unclosed token: line 2, column 14)

Dry run, nothing changed. Run again with --apply to move (add --copy to copy).
```

```bash
nfe-toolkit organize inbox organized --aplicar            # move
nfe-toolkit organize inbox organized --aplicar --copiar   # copia e mantém os originais
```

Regras:

- Nunca sobrescreve. Se o nome já existe, vira `_2`, `_3` e assim por diante.
- Detecta duplicados pela chave, inclusive contra o que já está em `DESTINO`, e os deixa onde
  estão.
- Arquivos ilegíveis ou com chave inválida são listados e ficam onde estão.
- `DESTINO` pode ficar dentro da pasta de origem (ou ser a mesma pasta): o que já está em
  `AAAA/MM/` não é mexido de novo, então rodar duas vezes não causa problema.
- `--apply` e `--copy` são os nomes em inglês das mesmas opções.

### `reconcile`: a pasta bate com a lista?

Compara uma pasta de XMLs com uma lista de chaves esperadas: `.txt` com uma chave por linha (`#`
inicia comentário) ou `.csv` com a coluna `chave` (também aceita `chave_acesso`, `chnfe`, `key` ou
`access_key`; separador vírgula, ponto e vírgula ou tab; UTF-8 ou Latin-1).

```console
$ nfe-toolkit reconcile inbox expected-keys.txt
Reconciliation of inbox against expected-keys.txt

  expected     4
  found        3
  missing      1
  extra        1
  duplicates   1
  invalid      2

MISSING (1)
  35260411222333000181550010000013051000013050

EXTRA, not in the list (1)
  35251111222333000181550010000009901000009906  inbox/nota-antiga.xml

DUPLICATES (1)
  35260311222333000181550010000012021000012028  xml: inbox/NF-1202.xml, inbox/downloads/NF-1202 (1).xml

INVALID (2)
  list line 6: 3526031122233300018155001  expected 44 digits, got 25
  inbox/corrompido.xml: malformed XML (unclosed token: line 2, column 14)

FAILED: missing keys.
```

Saída para outros programas:

```console
$ nfe-toolkit reconcile inbox expected-keys.txt --csv
status,key,location,detail
missing,35260411222333000181550010000013051000013050,,
extra,35251111222333000181550010000009901000009906,inbox/nota-antiga.xml,
duplicate,35260311222333000181550010000012021000012028,inbox/NF-1202.xml | inbox/downloads/NF-1202 (1).xml,in xml
invalid,3526031122233300018155001,line 6,"expected 44 digits, got 25"
invalid,,inbox/corrompido.xml,"malformed XML (unclosed token: line 2, column 14)"
```

`--json` gera o mesmo conteúdo em JSON e `-o arquivo` grava o relatório em disco.

Códigos de saída, úteis em scripts e pipelines de CI:

| Código | Significado |
|--------|-------------|
| 0 | todas as chaves esperadas foram encontradas |
| 1 | falta pelo menos uma chave (com `--strict`: qualquer ocorrência) |
| 2 | erro de uso, ou a pasta ou a lista não puderam ser lidas |

## Uso como biblioteca

```python
from nfe_toolkit import (
    validar,
    decompor,
    calcular_dv,
    formatar,
    ler_nota,
    planejar,
    aplicar,
    conciliar,
)

validar("35260311222333000181550010000012011000012012")  # True
calcular_dv("3526031122233300018155001000001201100001201")  # 2

info = decompor("35260311222333000181550010000012011000012012")
info.uf, info.ano, info.mes, info.modelo_descricao, info.emitente_formatado
# ('SP', 2026, 3, 'NF-e', '11.222.333/0001-81')

nota = ler_nota("inbox/NF-1202.xml")
nota.chave, nota.emitente_nome, nota.valor_total, nota.autorizada

plano = planejar("inbox", "organized")  # só lê, devolve um Plano
resultado = aplicar(plano, copiar=True)  # copia; nunca sobrescreve

r = conciliar("inbox", "expected-keys.txt")
r.faltando, r.sobrando, r.duplicadas, r.invalidas, r.ok
```

Os erros herdam de `nfe_toolkit.NfeToolkitError` (`ChaveInvalidaError`, `NotaInvalidaError`,
`ListaInvalidaError`); `ler_nota` também pode levantar `OSError` para arquivos ilegíveis.

## Limitações conhecidas

- **CNPJ alfanumérico ainda não é suportado.** A chave precisa ter 44 dígitos; chaves com o novo
  CNPJ alfanumérico aparecem como inválidas.
- Não confere assinatura, não valida contra o XSD e não consulta a SEFAZ. Chave com dígito
  verificador certo é uma chave bem formada, não necessariamente uma nota autorizada. Para isso,
  veja o status do protocolo (`cStat`) mostrado pelo `info`.
- Arquivos de evento (cancelamento, carta de correção, `procEventoNFe`) não são lidos e aparecem
  como "not an NF-e/NFC-e document". Nota cancelada não é detectada pelo evento.
- Só NF-e (55) e NFC-e (65). Chaves de CT-e e MDF-e têm o mesmo formato e passam na validação, mas o
  XML delas não é interpretado.
- O ano da chave é sempre considerado 20AA.
- Cada XML é lido inteiro na memória (arquivos acima de 20 MB são recusados). DTD e declaração de
  entidades são recusadas de propósito.
- As pastas são processadas em sequência. Centenas de milhares de arquivos funcionam, mas demoram.

## Desenvolvimento

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest
```

Os fixtures dos testes são gerados por código (`tests/fabrica.py`), com dígito verificador válido e
dados inventados. Veja o [CONTRIBUTING.md](CONTRIBUTING.md).

## Licença

[MIT](LICENSE)
