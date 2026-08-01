"""End-to-end smoke tests for the rendering CLI, invoked as a subprocess the
way a skill's `shell` step would call it (mirrors ../tax_engine/tests/test_cli.py).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run_cli(command: str, payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "rendering", command],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )
    return json.loads(proc.stdout)


def test_invoice_draft_via_cli():
    result = _run_cli(
        "invoice_draft",
        {"usdc_amount": "800", "client_label": "Berlin", "month": 7, "link": "solana:abc", "language": "pt-BR"},
    )
    assert "800 USDC" in result["text"]
    assert "julho" in result["text"]


def test_detect_language_switch_via_cli():
    result = _run_cli("detect_language_switch", {"message": "switch to English please"})
    assert result["result"] == "switch_to_en"


def test_format_brl_primitive_via_cli():
    result = _run_cli("format_brl", {"value": "1234.5", "language": "pt-BR"})
    assert result["text"] == "R$ 1.234,50"


def test_format_brl_signed_loss_via_cli():
    result = _run_cli("format_brl", {"value": "-1234.5", "language": "en", "signed": True})
    assert "loss" in result["text"]


def test_format_usdc_primitive_via_cli():
    result = _run_cli("format_usdc", {"value": "800", "language": "en"})
    assert result["text"] == "800 USDC"


def test_format_date_primitive_via_cli():
    result = _run_cli("format_date", {"date": "2026-07-05", "language": "pt-BR"})
    assert result["text"] == "05/07/2026"


def test_carne_leao_summary_via_cli_english():
    result = _run_cli(
        "carne_leao_summary",
        {
            "base": "4336.00",
            "bracket_rate": "0.15",
            "tax_due": "450.12",
            "darf_code": "0190",
            "competencia_month": 6,
            "competencia_year": 2026,
            "vencimento": "2026-07-31",
            "language": "en",
        },
    )
    assert "R$4,336.00" in result["text"]
    assert "Carnê-Leão" in result["text"]
    assert "contador" in result["text"]
