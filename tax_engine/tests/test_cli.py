"""End-to-end smoke tests for the CLI entry point, invoked as a subprocess
exactly the way a skill's `shell` step would call it (CLAUDE.md Section 8.2:
messy-payment-style integration coverage, mocked/no live network).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(command: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "tax_engine", command],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    return json.loads(proc.stdout)


def test_carne_leao_via_cli():
    result = _run_cli(
        "carne_leao",
        {
            "gross_income": "8000",
            "dependents_count": 1,
            "competencia": "07/2026",
            "vencimento": "2026-08-31",
        },
    )
    assert result["tax_due"] == "1124.29"
    assert result["table_verified"] is True


def test_capital_gains_via_cli():
    result = _run_cli(
        "capital_gains",
        {
            "income_entries": [{"usdc_amount": "1000", "brl_value": "5000.00"}],
            "usdc_amount_disposed": "1000",
            "proceeds_brl": "6000.00",
        },
    )
    assert result["tax_due"] == "150.00"
    assert result["disposal"]["gain_or_loss_brl"] == "1000.00"


def test_threshold_watch_via_cli():
    result = _run_cli("threshold_watch", {"cumulative_volume_brl": "36000"})
    assert result["exceeded"] is True


def test_ptax_resolve_via_cli():
    result = _run_cli(
        "ptax_resolve",
        {
            "receipt_date": "2026-07-18",
            "quotes": {"2026-07-17": "5.5000"},
        },
    )
    assert result["date_used"] == "2026-07-17"
    assert result["fallback_rule_applied"] is True


def test_missing_command_exits_nonzero():
    proc = subprocess.run(
        [sys.executable, "-m", "tax_engine", "nonexistent"],
        input="{}",
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode != 0
