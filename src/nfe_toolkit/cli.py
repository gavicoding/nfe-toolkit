"""Command line interface: ``nfe-toolkit validate|info|organize|reconcile``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .chave import decompor, formatar, formatar_cnpj, formatar_cpf, limpar, motivo_invalidez
from .conciliar import Conciliacao, conciliar, para_csv, para_json
from .erros import NfeToolkitError
from .organizar import aplicar, planejar
from .xml import Nota, ler_nota

EXIT_OK = 0
EXIT_FALHA = 1
EXIT_ERRO = 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (NfeToolkitError, OSError) as erro:
        print(f"error: {_mensagem(erro)}", file=sys.stderr)
        return EXIT_ERRO
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nfe-toolkit",
        description="Validate, inspect, organize and reconcile NF-e/NFC-e XML files.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("validate", help="check one or more 44-digit access keys")
    p.add_argument("keys", nargs="*", metavar="KEY", help="access keys (reads stdin if omitted)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("info", help="show what is inside an access key or an XML file")
    p.add_argument("target", metavar="KEY_OR_FILE")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=_cmd_info)

    p = sub.add_parser("organize", help="sort XML files into DEST/YYYY/MM/ by access key")
    p.add_argument("source", type=Path, metavar="SOURCE")
    p.add_argument("dest", type=Path, metavar="DEST")
    modo = p.add_mutually_exclusive_group()
    modo.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="only show the plan (default)",
    )
    modo.add_argument(
        "--apply", "--aplicar", dest="apply", action="store_true", help="move the files"
    )
    p.add_argument(
        "--copy", "--copiar", action="store_true", help="with --apply, copy instead of moving"
    )
    p.add_argument("--no-recursive", action="store_true", help="do not look into subfolders")
    p.set_defaults(func=_cmd_organize, apply=False)

    p = sub.add_parser("reconcile", help="compare a folder of XML files with a list of keys")
    p.add_argument("folder", type=Path, metavar="FOLDER")
    p.add_argument("keys_file", type=Path, metavar="KEYS_FILE", help=".txt or .csv")
    formato = p.add_mutually_exclusive_group()
    formato.add_argument("--json", action="store_true", help="print JSON")
    formato.add_argument("--csv", action="store_true", help="print CSV")
    p.add_argument("-o", "--output", type=Path, help="write the report to a file")
    p.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on any finding, not only on missing keys",
    )
    p.add_argument("--no-recursive", action="store_true", help="do not look into subfolders")
    p.set_defaults(func=_cmd_reconcile)
    return parser


# validate ------------------------------------------------------------------


def _cmd_validate(args: argparse.Namespace) -> int:
    chaves = list(args.keys)
    if not chaves:
        chaves = [linha.strip() for linha in sys.stdin if linha.strip()]
    if not chaves:
        print("error: no access key given", file=sys.stderr)
        return EXIT_ERRO

    resultados = [(limpar(c), motivo_invalidez(c)) for c in chaves]
    if args.json:
        dados = [{"key": c, "valid": m is None, "reason": m} for c, m in resultados]
        print(json.dumps(dados, indent=2))
    else:
        for chave, motivo in resultados:
            if motivo is None:
                print(f"VALID    {chave}")
            else:
                print(f"INVALID  {chave}  ({motivo})")
    return EXIT_OK if all(m is None for _, m in resultados) else EXIT_FALHA


# info ----------------------------------------------------------------------


def _cmd_info(args: argparse.Namespace) -> int:
    alvo = Path(args.target)
    if alvo.is_file():
        nota = ler_nota(alvo)
        info = decompor(nota.chave) if nota.chave_valida else None
        if args.json:
            dados = nota.as_dict()
            dados["key_fields"] = info.as_dict() if info else None
            print(json.dumps(dados, indent=2, ensure_ascii=False))
        else:
            _imprimir_nota(nota)
            if info:
                print()
                _imprimir_campos(_campos_chave(info))
        return EXIT_OK if nota.chave_valida else EXIT_FALHA

    motivo = motivo_invalidez(args.target)
    if motivo:
        if alvo.suffix.lower() == ".xml" or any(sep in args.target for sep in "/\\"):
            raise NfeToolkitError(f"file not found: {alvo}")
        print(f"error: invalid access key: {motivo}", file=sys.stderr)
        return EXIT_FALHA
    info = decompor(args.target)
    if args.json:
        print(json.dumps(info.as_dict(), indent=2))
    else:
        _imprimir_campos(_campos_chave(info))
    return EXIT_OK


def _campos_chave(info) -> list[tuple[str, str]]:
    return [
        ("Access key", formatar(info.chave)),
        ("State", f"{info.cuf} ({info.uf or 'unknown'})"),
        ("Year/month", f"{info.ano:04d}-{info.mes:02d}"),
        ("Issuer", f"{info.emitente_tipo} {info.emitente_formatado}"),
        ("Model", f"{info.modelo} ({info.modelo_descricao or 'unknown'})"),
        ("Series", str(info.serie)),
        ("Number", str(info.numero)),
        ("Emission type", f"{info.tp_emis} ({info.tp_emis_descricao or 'unknown'})"),
        ("Numeric code", info.cnf),
        ("Check digit", str(info.dv)),
    ]


def _imprimir_nota(nota: Nota) -> None:
    if nota.protocolo_status is None:
        protocolo = "none (note without authorization protocol)"
    else:
        protocolo = f"{nota.protocolo_status} {nota.protocolo_motivo or ''}".strip()
        if nota.protocolo_numero:
            protocolo += f" (nProt {nota.protocolo_numero})"
    destinatario = _pessoa(nota.destinatario_documento, nota.destinatario_nome)
    campos = [
        ("File", _rel(nota.arquivo) if nota.arquivo else "-"),
        ("Access key", nota.chave + ("" if nota.chave_valida else "  (INVALID)")),
        ("Issued at", nota.data_emissao or "-"),
        ("Issuer", _pessoa(nota.emitente_documento, nota.emitente_nome) or "-"),
        ("Recipient", destinatario or "-"),
        ("Total (vNF)", str(nota.valor_total) if nota.valor_total is not None else "-"),
        ("Protocol", protocolo),
    ]
    _imprimir_campos(campos)


def _pessoa(documento: str | None, nome: str | None) -> str:
    if documento and documento.isdigit() and len(documento) == 14:
        documento = formatar_cnpj(documento)
    elif documento and documento.isdigit() and len(documento) == 11:
        documento = formatar_cpf(documento)
    return " ".join(x for x in (documento, nome) if x)


def _imprimir_campos(campos: list[tuple[str, str]]) -> None:
    largura = max(len(nome) for nome, _ in campos)
    for nome, valor in campos:
        print(f"{nome.ljust(largura)}  {valor}")


# organize ------------------------------------------------------------------


def _cmd_organize(args: argparse.Namespace) -> int:
    if args.copy and not args.apply:
        print("note: --copy only takes effect together with --apply", file=sys.stderr)
    plano = planejar(args.source, args.dest, recursivo=not args.no_recursive)
    verbo = "copy" if args.copy else "move"

    titulo = "Plan" if not args.apply else "Applying"
    print(
        f"{titulo}: {len(plano.movimentos)} to {verbo}, "
        f"{len(plano.duplicados)} duplicate(s), {len(plano.falhas)} unreadable"
    )
    for mov in plano.movimentos:
        print(f"  {verbo}  {_rel(mov.origem)} -> {_rel(mov.destino)}")
    for dup in plano.duplicados:
        print(f"  skip  {_rel(dup.arquivo)} (same key as {_rel(dup.original)})")
    for falha in plano.falhas:
        print(f"  fail  {_rel(falha.arquivo)}: {falha.motivo}")

    if not args.apply:
        print("\nDry run, nothing changed. Run again with --apply to move (add --copy to copy).")
        return EXIT_OK

    resultado = aplicar(plano, copiar=args.copy)
    feito = "copied" if args.copy else "moved"
    print(f"\nDone: {len(resultado.feitos)} file(s) {feito}, {len(resultado.falhas)} error(s).")
    for falha in resultado.falhas:
        print(f"  error  {_rel(falha.arquivo)}: {falha.motivo}", file=sys.stderr)
    return EXIT_FALHA if resultado.falhas else EXIT_OK


# reconcile -----------------------------------------------------------------


def _cmd_reconcile(args: argparse.Namespace) -> int:
    resultado = conciliar(args.folder, args.keys_file, recursivo=not args.no_recursive)
    if args.json:
        texto = para_json(resultado) + "\n"
    elif args.csv:
        texto = para_csv(resultado)
    else:
        texto = _tabela(resultado, args.folder, args.keys_file)

    if args.output:
        args.output.write_text(texto, encoding="utf-8", newline="")
        print(f"report written to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(texto)

    if args.strict:
        return EXIT_OK if resultado.limpa else EXIT_FALHA
    return EXIT_OK if resultado.ok else EXIT_FALHA


def _tabela(resultado: Conciliacao, pasta: Path, lista: Path) -> str:
    linhas = [
        f"Reconciliation of {pasta} against {lista}",
        "",
        f"  expected     {resultado.esperadas}",
        f"  found        {resultado.encontradas}",
        f"  missing      {len(resultado.faltando)}",
        f"  extra        {len(resultado.sobrando)}",
        f"  duplicates   {len(resultado.duplicadas)}",
        f"  invalid      {len(resultado.invalidas)}",
    ]
    if resultado.faltando:
        linhas += ["", f"MISSING ({len(resultado.faltando)})"]
        linhas += [f"  {chave}" for chave in resultado.faltando]
    if resultado.sobrando:
        linhas += ["", f"EXTRA, not in the list ({len(resultado.sobrando)})"]
        linhas += [f"  {s.chave}  {_rel(s.arquivo)}" for s in resultado.sobrando]
    if resultado.duplicadas:
        linhas += ["", f"DUPLICATES ({len(resultado.duplicadas)})"]
        for dup in resultado.duplicadas:
            locais = ", ".join(_rel(Path(x)) if dup.origem == "xml" else x for x in dup.locais)
            linhas.append(f"  {dup.chave}  {dup.origem}: {locais}")
    if resultado.invalidas:
        linhas += ["", f"INVALID ({len(resultado.invalidas)})"]
        for inv in resultado.invalidas:
            local = _rel(Path(inv.local)) if inv.origem == "xml" else f"list {inv.local}"
            valor = f"{inv.valor}  " if inv.valor else ""
            linhas.append(f"  {local}: {valor}{inv.motivo}")
    linhas.append("")
    linhas.append("OK: every expected key was found." if resultado.ok else "FAILED: missing keys.")
    return "\n".join(linhas) + "\n"


# helpers -------------------------------------------------------------------


def _rel(caminho: Path) -> str:
    try:
        return Path(caminho).resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(caminho)


def _mensagem(erro: Exception) -> str:
    if isinstance(erro, OSError) and erro.filename:
        return f"{erro.strerror or erro}: {erro.filename}"
    return str(erro)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
