"""Smoke tests for the ledger validation CLI, invoked as a subprocess the
way a skill's `shell` step would call it before appending to the ledger.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(command: str, payload: dict, expect_success: bool = True):
    proc = subprocess.run(
        [sys.executable, "-m", "ledger", command],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if expect_success:
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)
    assert proc.returncode != 0
    return json.loads(proc.stderr)


def test_validate_accepts_a_correct_disposition_instruction():
    result = _run_cli(
        "validate",
        {
            "record_type": "disposition_instruction",
            "data": {
                "entry_id": "d1",
                "linked_income_entry_id": "e1",
                "instruction_source": "explicit_per_payment",
                "instruction": "hold_as_usdc",
                "confirmed_by_user_at": "2026-07-30T12:00:00",
            },
        },
    )
    assert result["valid"] is True
    assert "json_line" in result


def test_validate_rejects_missing_confirmation_and_exits_nonzero():
    result = _run_cli(
        "validate",
        {
            "record_type": "disposition_instruction",
            "data": {
                "entry_id": "d1",
                "linked_income_entry_id": "e1",
                "instruction_source": "explicit_per_payment",
                "instruction": "hold_as_usdc",
                "confirmed_by_user_at": None,
            },
        },
        expect_success=False,
    )
    assert result["valid"] is False
    assert "must not be null" in result["error"]


def test_validate_rejects_refund_draft_with_empty_address():
    result = _run_cli(
        "validate",
        {
            "record_type": "refund_draft",
            "data": {
                "draft_id": "r1",
                "linked_income_entry_id": "e1",
                "destination_address": "",
                "amount_usdc": "50",
                "confirmed_by_freelancer_at": "2026-07-30T12:00:00",
                "draft_tx": "unsigned-tx-blob",
            },
        },
        expect_success=False,
    )
    assert result["valid"] is False
