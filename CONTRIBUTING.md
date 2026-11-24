# Contributing

Bug reports and pull requests are welcome.

1. Open an issue first for anything bigger than a small fix, so we can agree on the approach.
2. Keep the runtime free of third-party dependencies. `pytest` and `ruff` are the only dev tools.
3. Add tests for every change, including the error paths. Build fixtures with `tests/fabrica.py`
   and use made-up data only: never commit real invoices, real CNPJ/CPF numbers or real names.
4. Before pushing:

   ```bash
   pip install -e ".[dev]"
   ruff check . && ruff format --check . && pytest
   ```

5. Write commit messages in the imperative ("Add CSV list support"), one topic per commit.

By contributing you agree that your work is released under the MIT license.
