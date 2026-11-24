# nfe-toolkit

[![CI](https://github.com/gavicoding/nfe-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/gavicoding/nfe-toolkit/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20to%203.13-blue)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

English | [Português](README.pt-BR.md)

Validate, inspect, organize and reconcile Brazilian e-invoice (NF-e / NFC-e) XML files from the
command line or from Python. Standard library only, nothing to install besides the package itself.

## The problem

Anyone who deals with NF-e and NFC-e (developers, accountants, IT support) keeps running into the
same chores:

- Is this 44-digit access key valid, or did someone mistype a digit?
- Whose invoice is this, and from when, if all I have is the key?
- There are thousands of loose XML files in a folder (or ten folders). Sort them by month.
- Which of them are duplicates?
- The accounting system says we issued these 3,000 invoices. Are all the XMLs really here?

Usually this ends up being done by hand or with a spreadsheet. `nfe-toolkit` does each of these
with one command, and the same functions are available as a library.

## Install

Requires Python 3.10 or newer.

```bash
pip install git+https://github.com/gavicoding/nfe-toolkit.git
```

Or from a clone:

```bash
git clone https://github.com/gavicoding/nfe-toolkit.git
cd nfe-toolkit
pip install .
```

This installs the `nfe-toolkit` command. `python -m nfe_toolkit` works too.

## Usage

The examples below run from inside the [`examples/`](examples/) folder, which has a few
fictitious XML files and a key list (regenerate them with `python examples/make_samples.py`). Every company, document number and value in them is made up.

### `validate`: check access keys

Checks length, digits only and the modulo 11 check digit. Spaces, dots and a leading `NFe` are
ignored, so you can paste a key straight from a DANFE. Keys can also come from stdin, one per line.

```console
$ nfe-toolkit validate 35260311222333000181550010000012011000012012 \
    "3526 0311 2223 3300 0181 5500 1000 0012 0111 0000 1200" 3526031122233300018155
VALID    35260311222333000181550010000012011000012012
INVALID  35260311222333000181550010000012011100001200  (check digit mismatch (expected 9, got 0))
INVALID  3526031122233300018155  (expected 44 digits, got 22)
$ echo $?
1
```

```bash
cut -d';' -f1 keys.csv | nfe-toolkit validate --json > report.json
```

### `info`: what is inside a key or an XML

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

Given a file, it reads the XML (bare `<NFe>` or `<nfeProc>`, with or without namespace) and adds
the issuer, recipient, total and authorization protocol:

```console
$ nfe-toolkit info inbox/35260311222333000181550010000012011000012012-procNFe.xml
File         inbox/35260311222333000181550010000012011000012012-procNFe.xml
Access key   35260311222333000181550010000012011000012012
Issued at    2026-03-02T10:12:00-03:00
Issuer       11.222.333/0001-81 Empresa Exemplo Ltda
Recipient    123.456.789-09 Cliente Exemplo
Total (vNF)  1520.40
Protocol     100 Autorizado o uso da NF-e (nProt 135260000001201)

Access key     3526 0311 2223 3300 0181 5500 1000 0012 0110 0001 2012
State          35 (SP)
...
```

A broken file gives a one-line error and exit code 2, not a stack trace:

```console
$ nfe-toolkit info inbox/corrompido.xml
error: inbox/corrompido.xml: malformed XML (unclosed token: line 2, column 14)
```

Add `--json` to get everything as JSON.

### `organize`: sort XML files into `DEST/YYYY/MM/`

The year and month come from the access key. **Dry run is the default**: it only prints the plan.

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
nfe-toolkit organize inbox organized --apply          # move
nfe-toolkit organize inbox organized --apply --copy   # copy, keep the originals
```

Rules:

- Existing files are never overwritten. A name already taken gets `_2`, `_3`, and so on.
- Duplicates (same access key) are detected, including against files already in `DEST`, and left
  where they are.
- Unreadable files and files with an invalid key are reported and left where they are.
- `DEST` can be inside the source folder (or be the same folder); files already in `YYYY/MM/` are
  not touched again, so running twice is safe.
- `--aplicar` and `--copiar` are accepted as aliases of `--apply` and `--copy`.

### `reconcile`: does the folder match the list?

Compares a folder of XML files with a list of expected keys: a `.txt` with one key per line (`#`
starts a comment) or a `.csv` with a `chave` column (also `chave_acesso`, `chnfe`, `key` or
`access_key`; comma, semicolon or tab, UTF-8 or Latin-1).

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

Machine-readable output:

```console
$ nfe-toolkit reconcile inbox expected-keys.txt --csv
status,key,location,detail
missing,35260411222333000181550010000013051000013050,,
extra,35251111222333000181550010000009901000009906,inbox/nota-antiga.xml,
duplicate,35260311222333000181550010000012021000012028,inbox/NF-1202.xml | inbox/downloads/NF-1202 (1).xml,in xml
invalid,3526031122233300018155001,line 6,"expected 44 digits, got 25"
invalid,,inbox/corrompido.xml,"malformed XML (unclosed token: line 2, column 14)"
```

```console
$ nfe-toolkit reconcile inbox expected-keys.txt --json -o report.json
report written to report.json
$ head -9 report.json
{
  "summary": {
    "expected": 4,
    "found": 3,
    "missing": 1,
    "extra": 1,
    "duplicates": 1,
    "invalid": 2
  },
```

Exit codes, handy in scripts and CI jobs:

| Code | Meaning |
|------|---------|
| 0 | every expected key was found |
| 1 | at least one key is missing (with `--strict`: any finding at all) |
| 2 | usage error, or the folder or list could not be read |

## Use as a library

```python
from nfe_toolkit import validar, decompor, calcular_dv, formatar, ler_nota, planejar, aplicar, conciliar

validar("35260311222333000181550010000012011000012012")      # True
calcular_dv("3526031122233300018155001000001201100001201")   # 2
formatar("35260311222333000181550010000012011000012012")
# '3526 0311 2223 3300 0181 5500 1000 0012 0110 0001 2012'

info = decompor("35260311222333000181550010000012011000012012")
info.uf, info.ano, info.mes, info.modelo_descricao, info.emitente_formatado
# ('SP', 2026, 3, 'NF-e', '11.222.333/0001-81')

nota = ler_nota("inbox/NF-1202.xml")
nota.chave, nota.emitente_nome, nota.valor_total, nota.autorizada
# ('3526031122...', 'Empresa Exemplo Ltda', Decimal('89.90'), False)

plano = planejar("inbox", "organized")      # reads only, returns a Plano
for mov in plano.movimentos:
    print(mov.origem, "->", mov.destino)
resultado = aplicar(plano, copiar=True)     # copies; never overwrites

r = conciliar("inbox", "expected-keys.txt")
r.faltando, r.sobrando, r.duplicadas, r.invalidas, r.ok
```

The API names are in Portuguese, the vocabulary of the domain (`chave`, `nota`, `emitente`).
Errors derive from `nfe_toolkit.NfeToolkitError` (`ChaveInvalidaError`, `NotaInvalidaError`,
`ListaInvalidaError`); `ler_nota` may also raise `OSError` for unreadable files.

## Known limitations

- **Alphanumeric CNPJ is not supported yet.** Keys must be 44 digits; keys carrying the new
  alphanumeric CNPJ format are reported as invalid.
- No signature check, no XSD schema validation and no SEFAZ lookup. A key with a correct check
  digit is well formed, not necessarily an authorized invoice. Use the protocol status (`cStat`)
  shown by `info` for that.
- Event files (cancellation, correction letter, `procEventoNFe`) are not read; they show up as
  "not an NF-e/NFC-e document". A cancelled invoice is not detected from its event.
- Only NF-e (55) and NFC-e (65). CT-e and MDF-e keys have the same layout and will validate, but
  their XML is not parsed.
- The year from the key is assumed to be 20YY.
- Each XML is parsed whole in memory (files over 20 MB are rejected). DTDs and entity declarations
  are refused on purpose.
- Folders are processed sequentially. Hundreds of thousands of files work, but take a while.

## Development

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest
```

The test fixtures are built by code (`tests/fabrica.py`), with valid check digits and made-up data.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
