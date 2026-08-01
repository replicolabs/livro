import json
from decimal import Decimal

from gate.balance import load_debits
from gate.cost_reconciler import reconcile_tenant_costs


def _cost_record(record_id: str, agent_alias: str, cost_usd: float) -> dict:
    """Shape matches the real ZeroClaw CostRecord struct, confirmed against
    crates/zeroclaw-config/src/cost/types.rs:133 (id, usage.cost_usd,
    session_id, agent_alias, task_id).
    """
    return {
        "id": record_id,
        "usage": {
            "model": "claude-sonnet-5",
            "input_tokens": 1000,
            "output_tokens": 200,
            "cached_input_tokens": 0,
            "total_tokens": 1200,
            "cost_usd": cost_usd,
            "pricing_available": True,
            "timestamp": "2026-08-01T12:00:00Z",
        },
        "session_id": "sess_1",
        "agent_alias": agent_alias,
        "task_id": None,
    }


def _write_costs_jsonl(path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_reconcile_creates_debits_only_for_matching_tenant(tmp_path):
    costs_path = tmp_path / "costs.jsonl"
    _write_costs_jsonl(costs_path, [
        _cost_record("cost_1", "t_1", 0.05),
        _cost_record("cost_2", "t_2", 0.10),  # different tenant, ignored
        _cost_record("cost_3", "t_1", 0.03),
    ])

    written = reconcile_tenant_costs(tmp_path, costs_path, "t_1")

    assert written == 2
    debits = load_debits(tmp_path, "t_1")
    assert len(debits) == 2
    assert {d.usd_amount for d in debits} == {Decimal("0.05"), Decimal("0.03")}
    assert {d.cost_record_ref for d in debits} == {"cost_1", "cost_3"}


def test_reconcile_is_idempotent_no_double_debit(tmp_path):
    costs_path = tmp_path / "costs.jsonl"
    _write_costs_jsonl(costs_path, [_cost_record("cost_1", "t_1", 0.05)])

    first_pass = reconcile_tenant_costs(tmp_path, costs_path, "t_1")
    second_pass = reconcile_tenant_costs(tmp_path, costs_path, "t_1")

    assert first_pass == 1
    assert second_pass == 0  # already debited, no duplicate
    assert len(load_debits(tmp_path, "t_1")) == 1


def test_reconcile_picks_up_new_lines_appended_since_last_pass(tmp_path):
    costs_path = tmp_path / "costs.jsonl"
    _write_costs_jsonl(costs_path, [_cost_record("cost_1", "t_1", 0.05)])
    reconcile_tenant_costs(tmp_path, costs_path, "t_1")

    with costs_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(_cost_record("cost_2", "t_1", 0.02)) + "\n")

    written = reconcile_tenant_costs(tmp_path, costs_path, "t_1")
    assert written == 1
    assert len(load_debits(tmp_path, "t_1")) == 2


def test_reconcile_ignores_zero_cost_records(tmp_path):
    costs_path = tmp_path / "costs.jsonl"
    _write_costs_jsonl(costs_path, [_cost_record("cost_1", "t_1", 0.0)])

    written = reconcile_tenant_costs(tmp_path, costs_path, "t_1")
    assert written == 0
    assert load_debits(tmp_path, "t_1") == []


def test_reconcile_ignores_records_with_no_agent_alias(tmp_path):
    """Records predating per-agent attribution, or track_per_agent=false --
    agent_alias is None, can't be attributed to any tenant, skip silently
    rather than crash.
    """
    costs_path = tmp_path / "costs.jsonl"
    record = _cost_record("cost_1", "t_1", 0.05)
    record["agent_alias"] = None
    _write_costs_jsonl(costs_path, [record])

    written = reconcile_tenant_costs(tmp_path, costs_path, "t_1")
    assert written == 0


def test_reconcile_missing_costs_file_returns_zero(tmp_path):
    written = reconcile_tenant_costs(tmp_path, tmp_path / "nonexistent.jsonl", "t_1")
    assert written == 0


def test_reconcile_handles_partial_final_line_gracefully(tmp_path):
    """A concurrently-written costs.jsonl can have a partially-flushed
    final line when read mid-write -- must not crash, just skip it.
    """
    costs_path = tmp_path / "costs.jsonl"
    with costs_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(_cost_record("cost_1", "t_1", 0.05)) + "\n")
        f.write('{"id": "cost_2", "usage": {"cost_usd"')  # truncated, no newline

    written = reconcile_tenant_costs(tmp_path, costs_path, "t_1")
    assert written == 1  # only the complete record
