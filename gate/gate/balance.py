"""TenantBalance derivation and the pre-turn spend-prevention gate check.

Storage is two append-only JSONL files under the gate's own `platform/`
directory (topups.jsonl, debits.jsonl) -- consistent with Livro's existing
"no bespoke database" philosophy (DEVIATIONS.md Section 1), not a new one
invented for billing.

The gate check is deliberately coarse: the exact cost of a turn isn't known
until it finishes and ZeroClaw writes a costs.jsonl record (see
cost_reconciler.py), so a tenant can go slightly negative on one expensive
turn before the next pre-turn check catches it. MIN_BALANCE_FLOOR is that
tolerance, made an explicit policy rather than an accidental gap.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ledger.serialization import to_json_line
from platform_ledger.records import CreditDebit, CreditTopUp, compute_balance

MIN_BALANCE_FLOOR = Decimal("-0.50")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_topups(platform_dir: Path, tenant_id: str) -> list[CreditTopUp]:
    result = []
    for r in _read_jsonl(platform_dir / "topups.jsonl"):
        if r["tenant_id"] != tenant_id:
            continue
        result.append(
            CreditTopUp(
                topup_id=r["topup_id"],
                tenant_id=r["tenant_id"],
                reference_key=r["reference_key"],
                usdc_amount=Decimal(r["usdc_amount"]),
                credited_usd_balance_delta=Decimal(r["credited_usd_balance_delta"]),
                confirmed_at=datetime.fromisoformat(r["confirmed_at"]),
                source=r["source"],
                tx_signature=r.get("tx_signature"),
            )
        )
    return result


def load_debits(platform_dir: Path, tenant_id: str) -> list[CreditDebit]:
    result = []
    for r in _read_jsonl(platform_dir / "debits.jsonl"):
        if r["tenant_id"] != tenant_id:
            continue
        result.append(
            CreditDebit(
                debit_id=r["debit_id"],
                tenant_id=r["tenant_id"],
                cost_record_ref=r["cost_record_ref"],
                usd_amount=Decimal(r["usd_amount"]),
                debited_at=datetime.fromisoformat(r["debited_at"]),
            )
        )
    return result


def get_balance(platform_dir: Path, tenant_id: str) -> Decimal:
    return compute_balance(load_topups(platform_dir, tenant_id), load_debits(platform_dir, tenant_id))


def check_balance_gate(platform_dir: Path, tenant_id: str, floor: Decimal = MIN_BALANCE_FLOOR) -> bool:
    """True if this tenant's message may proceed to ZeroClaw."""
    return get_balance(platform_dir, tenant_id) > floor


def append_topup(platform_dir: Path, topup: CreditTopUp) -> None:
    platform_dir.mkdir(parents=True, exist_ok=True)
    with (platform_dir / "topups.jsonl").open("a", encoding="utf-8") as f:
        f.write(to_json_line(topup) + "\n")


def append_debit(platform_dir: Path, debit: CreditDebit) -> None:
    platform_dir.mkdir(parents=True, exist_ok=True)
    with (platform_dir / "debits.jsonl").open("a", encoding="utf-8") as f:
        f.write(to_json_line(debit) + "\n")
