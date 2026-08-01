"""JSON-in/JSON-out CLI so skill/SOP step instructions can invoke the pure
tax engine via the stock `shell` tool (see DEVIATIONS.md Section 7).

Every subcommand reads one JSON object from stdin and writes one JSON object
to stdout. No subcommand performs network I/O or writes to the ledger --
callers (skills) own reading/appending the workspace ledger JSONL files; this
CLI only computes. Ledger replay (folding income/disposal JSONL history into
a CostBasisPool) is provided as a convenience since it is a deterministic,
pure operation over a well-defined file format, not a side effect.

Usage:
    echo '{...}' | python3 -m tax_engine carne_leao
    echo '{...}' | python3 -m tax_engine capital_gains
    echo '{...}' | python3 -m tax_engine threshold_watch
    echo '{...}' | python3 -m tax_engine ptax_resolve
    echo '{...}' | python3 -m tax_engine cost_basis_dispose
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from tax_engine.capital_gains import compute_capital_gains
from tax_engine.carne_leao import CarneLeaoDeductions, compute_carne_leao
from tax_engine.cost_basis import CostBasisPool
from tax_engine.ptax import resolve_ptax_rate
from tax_engine.tables import load_table
from tax_engine.threshold_watch import check_threshold


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def _read_stdin_json() -> dict:
    raw = sys.stdin.read()
    return json.loads(raw)


def _emit(result: Any) -> None:
    print(json.dumps(_to_jsonable(result), ensure_ascii=False, indent=2))


def _cmd_carne_leao(args: dict) -> Any:
    table = load_table(args.get("table_file", "carne_leao_2026.json"))
    deductions = CarneLeaoDeductions(
        inss_monthly=Decimal(str(args.get("inss_monthly", "0"))),
        dependents_count=int(args.get("dependents_count", 0)),
        alimony_monthly=Decimal(str(args.get("alimony_monthly", "0"))),
        livro_caixa_expenses_monthly=Decimal(str(args.get("livro_caixa_expenses_monthly", "0"))),
    )
    return compute_carne_leao(
        gross_income=Decimal(str(args["gross_income"])),
        deductions=deductions,
        table=table,
        competencia=args["competencia"],
        vencimento=args["vencimento"],
    )


def _cmd_capital_gains(args: dict) -> Any:
    table = load_table(args.get("table_file", "capital_gains_2026.json"))
    pool = _replay_pool(args["income_entries"], args.get("prior_disposals", []))
    disposal = pool.dispose(
        Decimal(str(args["usdc_amount_disposed"])),
        proceeds_brl=Decimal(str(args["proceeds_brl"])),
    )
    return compute_capital_gains(disposal, table)


def _cmd_cost_basis_dispose(args: dict) -> Any:
    pool = _replay_pool(args["income_entries"], args.get("prior_disposals", []))
    return pool.dispose(
        Decimal(str(args["usdc_amount_disposed"])),
        proceeds_brl=Decimal(str(args["proceeds_brl"])),
    )


def _replay_pool(income_entries: list[dict], prior_disposals: list[dict]) -> CostBasisPool:
    """Reconstruct a CostBasisPool from ledger-shaped income/disposal records.

    income_entries: [{"usdc_amount": "...", "brl_value": "..."}, ...]
    prior_disposals: [{"usdc_amount_disposed": "...", "proceeds_brl": "..."}, ...]
    Replayed in the order given -- callers must pass entries in chronological
    order (the ledger is append-only, so file order already satisfies this).
    """
    pool = CostBasisPool()
    for entry in income_entries:
        pool.add_income(Decimal(str(entry["usdc_amount"])), Decimal(str(entry["brl_value"])))
    for disposal in prior_disposals:
        pool.dispose(
            Decimal(str(disposal["usdc_amount_disposed"])),
            proceeds_brl=Decimal(str(disposal["proceeds_brl"])),
        )
    return pool


def _cmd_threshold_watch(args: dict) -> Any:
    table = load_table(args.get("table_file", "in1888_threshold_2026.json"))
    return check_threshold(Decimal(str(args["cumulative_volume_brl"])), table)


def _cmd_ptax_resolve(args: dict) -> Any:
    """quotes: {"YYYY-MM-DD": "rate", ...} -- the caller (skill glue) fetches
    the Olinda PTAX window via http_request and passes the parsed quotes in;
    this command only applies the fallback-day-selection rule.
    """
    quotes = {date.fromisoformat(k): Decimal(str(v)) for k, v in args["quotes"].items()}

    def lookup(d: date):
        return quotes.get(d)

    return resolve_ptax_rate(
        date.fromisoformat(args["receipt_date"]),
        lookup,
        quote_type=args.get("quote_type", "venda"),
        max_lookback_days=int(args.get("max_lookback_days", 10)),
    )


COMMANDS = {
    "carne_leao": _cmd_carne_leao,
    "capital_gains": _cmd_capital_gains,
    "cost_basis_dispose": _cmd_cost_basis_dispose,
    "threshold_watch": _cmd_threshold_watch,
    "ptax_resolve": _cmd_ptax_resolve,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python3 -m tax_engine <{'|'.join(COMMANDS)}> < args.json", file=sys.stderr)
        return 2

    args = _read_stdin_json()
    try:
        result = COMMANDS[argv[0]](args)
    except (KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    _emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
