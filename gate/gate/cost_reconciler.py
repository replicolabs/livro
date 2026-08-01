"""Tails ZeroClaw's own costs.jsonl and converts new per-tenant records into
CreditDebit entries -- reusing ZeroClaw's real Anthropic cost accounting
(CostRecord, confirmed at crates/zeroclaw-config/src/cost/types.rs:133,
`usage.cost_usd` field) rather than reimplementing pricing math ourselves.

costs.jsonl is ONE shared file for the whole daemon (`track_per_agent`
confirmed `true` by default at schema.rs:6555 -- it adds an `agent_alias`
field to each record, it doesn't split the file), so this module filters by
`agent_alias == tenant_id` on every pass. It re-scans the whole file each
call and dedupes against already-written CreditDebit.cost_record_ref values
(each CostRecord's own `id` field) rather than tracking a byte offset --
simple and correct; an offset-based optimization is a fine later
improvement once file size is actually a problem, not before.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from platform_ledger.records import CreditDebit

from gate.balance import append_debit, load_debits


def reconcile_tenant_costs(platform_dir: Path, costs_jsonl_path: Path, tenant_id: str) -> int:
    """Returns the number of new CreditDebit records written."""
    already_debited_refs = {d.cost_record_ref for d in load_debits(platform_dir, tenant_id)}

    if not costs_jsonl_path.exists():
        return 0

    written = 0
    with costs_jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # a partially-flushed final line; skip, will be complete next pass

            if record.get("agent_alias") != tenant_id:
                continue

            cost_record_ref = record.get("id")
            if not cost_record_ref or cost_record_ref in already_debited_refs:
                continue

            usage = record.get("usage", {})
            cost_usd = Decimal(str(usage.get("cost_usd", 0)))
            if cost_usd <= 0:
                continue  # nothing to debit for a zero-cost or free-tier record

            debit = CreditDebit(
                debit_id=f"debit_{uuid.uuid4().hex[:12]}",
                tenant_id=tenant_id,
                cost_record_ref=cost_record_ref,
                usd_amount=cost_usd,
                debited_at=datetime.now(timezone.utc),
            )
            append_debit(platform_dir, debit)
            already_debited_refs.add(cost_record_ref)
            written += 1

    return written
