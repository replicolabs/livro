"""JSON-in/JSON-out CLI so skill/SOP step instructions can render bilingual
messages via the stock `shell` tool, the same pattern as ../tax_engine/.

Usage:
    echo '{...}' | python3 -m rendering invoice_draft
    echo '{...}' | python3 -m rendering payment_received
    echo '{...}' | python3 -m rendering carne_leao_summary
    echo '{...}' | python3 -m rendering threshold_warning
    echo '{...}' | python3 -m rendering injection_refusal
    echo '{...}' | python3 -m rendering external_holding_prompt
    echo '{...}' | python3 -m rendering language_switch_confirmation
    echo '{...}' | python3 -m rendering language_switch_clarification
    echo '{...}' | python3 -m rendering detect_language_switch
    echo '{...}' | python3 -m rendering format_brl
    echo '{...}' | python3 -m rendering format_usdc
    echo '{...}' | python3 -m rendering format_date
"""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal

from rendering.formatting import format_brl, format_brl_signed, format_date, format_usdc
from rendering.language_switch import detect_language_switch
from rendering.templates import (
    render_disposition_choices,
    render_external_holding_prompt,
    render_injection_refusal,
    render_invoice_draft,
    render_language_switch_clarification,
    render_language_switch_confirmation,
    render_monthly_carne_leao_summary,
    render_payment_received,
    render_threshold_warning,
)


def _cmd_invoice_draft(a: dict) -> dict:
    text = render_invoice_draft(
        Decimal(str(a["usdc_amount"])), a["client_label"], int(a["month"]), a["link"], a["language"]
    )
    return {"text": text}


def _cmd_payment_received(a: dict) -> dict:
    text = render_payment_received(
        Decimal(str(a["usdc_amount"])),
        a["client_label"],
        date.fromisoformat(a["receipt_date"]),
        Decimal(str(a["ptax_rate"])),
        Decimal(str(a["brl_value"])),
        a["language"],
    )
    return {"text": text}


def _cmd_carne_leao_summary(a: dict) -> dict:
    text = render_monthly_carne_leao_summary(
        Decimal(str(a["base"])),
        Decimal(str(a["bracket_rate"])),
        Decimal(str(a["tax_due"])),
        a["darf_code"],
        int(a["competencia_month"]),
        int(a["competencia_year"]),
        date.fromisoformat(a["vencimento"]),
        a["language"],
    )
    return {"text": text}


def _cmd_threshold_warning(a: dict) -> dict:
    return {"text": render_threshold_warning(Decimal(str(a["threshold_brl"])), a["language"])}


def _cmd_injection_refusal(a: dict) -> dict:
    return {"text": render_injection_refusal(a["language"])}


def _cmd_external_holding_prompt(a: dict) -> dict:
    return {"text": render_external_holding_prompt(a["language"])}


def _cmd_disposition_choices(a: dict) -> dict:
    return {"choices": render_disposition_choices(a["language"])}


def _cmd_language_switch_confirmation(a: dict) -> dict:
    return {"text": render_language_switch_confirmation(a["new_language"])}


def _cmd_language_switch_clarification(a: dict) -> dict:
    return {"text": render_language_switch_clarification(a["current_language"])}


def _cmd_detect_language_switch(a: dict) -> dict:
    return {"result": detect_language_switch(a["message"])}


def _cmd_format_brl(a: dict) -> dict:
    """Primitive formatter for skills with no dedicated message template
    (docs/language.md Section 6 doesn't specify one for every possible
    message, e.g. draft_refund/draft_bond_allocation/annual_summary/
    export_for_contador) -- so ad-hoc figures in freehand prose still go
    through the tested locale formatter rather than inline string building.
    Pass `"signed": true` for a possibly-negative amount (gain/loss) to get
    the explicit loss-label rendering instead of a bare minus sign.
    """
    value = Decimal(str(a["value"]))
    if a.get("signed"):
        return {"text": format_brl_signed(value, a["language"])}
    return {"text": format_brl(value, a["language"])}


def _cmd_format_usdc(a: dict) -> dict:
    return {"text": format_usdc(Decimal(str(a["value"])), a["language"])}


def _cmd_format_date(a: dict) -> dict:
    return {"text": format_date(date.fromisoformat(a["date"]), a["language"])}


COMMANDS = {
    "invoice_draft": _cmd_invoice_draft,
    "payment_received": _cmd_payment_received,
    "carne_leao_summary": _cmd_carne_leao_summary,
    "threshold_warning": _cmd_threshold_warning,
    "injection_refusal": _cmd_injection_refusal,
    "external_holding_prompt": _cmd_external_holding_prompt,
    "disposition_choices": _cmd_disposition_choices,
    "language_switch_confirmation": _cmd_language_switch_confirmation,
    "language_switch_clarification": _cmd_language_switch_clarification,
    "detect_language_switch": _cmd_detect_language_switch,
    "format_brl": _cmd_format_brl,
    "format_usdc": _cmd_format_usdc,
    "format_date": _cmd_format_date,
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: python3 -m rendering <{'|'.join(COMMANDS)}> < args.json", file=sys.stderr)
        return 2

    args = json.loads(sys.stdin.read())
    try:
        result = COMMANDS[argv[0]](args)
    except (KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
