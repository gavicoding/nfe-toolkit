# Changelog

## 1.0.0 (2026-11-24)

First release.

- `validate`: 44-digit access key check with modulo 11 check digit, text or JSON output, stdin.
- `info`: decode a key (state, year/month, issuer CNPJ/CPF, model, series, number, emission type)
  or read an NF-e/NFC-e XML (`NFe` or `nfeProc`, any namespace).
- `organize`: sort XML files into `DEST/YYYY/MM/`, dry run by default, move or copy, never
  overwrites, detects duplicates by key.
- `reconcile`: compare a folder with a `.txt` or `.csv` key list; table, JSON or CSV report and a
  non-zero exit code when keys are missing.
- Python API with the same functions; no runtime dependencies.
