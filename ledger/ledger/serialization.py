"""JSON round-tripping for ledger records -- the append-only JSONL file
format itself (CLAUDE.md Section 4, DEVIATIONS.md Section 1). Construction
validation lives in records.py; this module only converts to/from the wire
shape, and always goes through the record's own __post_init__ on the way
back in, so a corrupted or hand-edited JSONL line still gets caught.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Type, TypeVar

from ledger.records import (
    BondPosition,
    DisposalEntry,
    DispositionInstruction,
    ExternalHolding,
    FxRateUsed,
    IncomeEntry,
    PaymentException,
    RefundDraft,
)

T = TypeVar("T")


def to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, (tuple, list)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    return obj


def to_json_line(record: Any) -> str:
    """One append-only JSONL line -- CLAUDE.md's own format for the ledger."""
    return json.dumps(to_jsonable(record), ensure_ascii=False)


def _dec(v) -> Decimal:
    return Decimal(str(v))


def _date(v) -> date:
    return date.fromisoformat(v) if isinstance(v, str) else v


def _dt(v) -> datetime:
    return datetime.fromisoformat(v) if isinstance(v, str) else v


def income_entry_from_dict(data: dict) -> IncomeEntry:
    fx = data["fx_rate_used"]
    return IncomeEntry(
        entry_id=data["entry_id"],
        tx_signature=data["tx_signature"],
        reference_key=data["reference_key"],
        receiving_address=data["receiving_address"],
        client_label=data["client_label"],
        usdc_amount=_dec(data["usdc_amount"]),
        receipt_date=_date(data["receipt_date"]),
        receipt_classification=data["receipt_classification"],
        expected_amount=_dec(data["expected_amount"]),
        fx_rate=_dec(data["fx_rate"]),
        fx_rate_used=FxRateUsed(
            source=fx["source"],
            endpoint_queried=fx["endpoint_queried"],
            quote_type=fx["quote_type"],
            date_of_quote=_date(fx["date_of_quote"]),
            fallback_rule_applied=bool(fx["fallback_rule_applied"]),
        ),
        brl_value=_dec(data["brl_value"]),
        created_at=_dt(data["created_at"]),
        notes=data.get("notes", ""),
    )


def disposition_instruction_from_dict(data: dict) -> DispositionInstruction:
    return DispositionInstruction(
        entry_id=data["entry_id"],
        linked_income_entry_id=data["linked_income_entry_id"],
        instruction_source=data["instruction_source"],
        instruction=data["instruction"],
        confirmed_by_user_at=_dt(data["confirmed_by_user_at"]),
        allocation_details=data.get("allocation_details"),
    )


def disposal_entry_from_dict(data: dict) -> DisposalEntry:
    return DisposalEntry(
        entry_id=data["entry_id"],
        linked_income_entry_ids=tuple(data["linked_income_entry_ids"]),
        disposal_date=_date(data["disposal_date"]),
        disposal_reason=data["disposal_reason"],
        usdc_amount_disposed=_dec(data["usdc_amount_disposed"]),
        cost_basis_brl=_dec(data["cost_basis_brl"]),
        proceeds_brl=_dec(data["proceeds_brl"]),
        gain_or_loss_brl=_dec(data["gain_or_loss_brl"]),
        regime_applied=data["regime_applied"],
        created_at=_dt(data["created_at"]),
    )


def bond_position_from_dict(data: dict) -> BondPosition:
    return BondPosition(
        position_id=data["position_id"],
        linked_disposal_entry_id=data["linked_disposal_entry_id"],
        bond=data["bond"],
        provider=data["provider"],
        amount_allocated_usdc_equivalent=_dec(data["amount_allocated_usdc_equivalent"]),
        draft_tx=data["draft_tx"],
        status=data.get("status", "drafted"),
        tax_treatment_flag=data.get("tax_treatment_flag", "novel_asset_class_unresolved"),
    )


def payment_exception_from_dict(data: dict) -> PaymentException:
    return PaymentException(
        exception_id=data["exception_id"],
        linked_income_entry_id=data["linked_income_entry_id"],
        kind=data["kind"],
        detail=data["detail"],
        resolution_status=data.get("resolution_status", "pending_freelancer_decision"),
        resolution=data.get("resolution"),
        resolved_at=_dt(data["resolved_at"]) if data.get("resolved_at") else None,
    )


def refund_draft_from_dict(data: dict) -> RefundDraft:
    return RefundDraft(
        draft_id=data["draft_id"],
        linked_income_entry_id=data["linked_income_entry_id"],
        destination_address=data["destination_address"],
        amount_usdc=_dec(data["amount_usdc"]),
        confirmed_by_freelancer_at=_dt(data["confirmed_by_freelancer_at"]),
        draft_tx=data["draft_tx"],
        status=data.get("status", "drafted"),
    )


def external_holding_from_dict(data: dict) -> ExternalHolding:
    return ExternalHolding(
        holding_id=data["holding_id"],
        declared_by_user_at=_dt(data["declared_by_user_at"]),
        asset=data["asset"],
        amount=_dec(data["amount"]),
        approx_receipt_date=_date(data["approx_receipt_date"]),
        rate_used=_dec(data["rate_used"]),
        brl_value=_dec(data["brl_value"]),
        provenance=data.get("provenance", "declared_by_user"),
        notes=data.get("notes", ""),
    )


FROM_DICT_BY_RECORD_TYPE = {
    "income_entry": income_entry_from_dict,
    "disposition_instruction": disposition_instruction_from_dict,
    "disposal_entry": disposal_entry_from_dict,
    "bond_position": bond_position_from_dict,
    "payment_exception": payment_exception_from_dict,
    "refund_draft": refund_draft_from_dict,
    "external_holding": external_holding_from_dict,
}


def from_dict(record_type: str, data: dict):
    """Reconstruct and re-validate a record from a raw dict (e.g. a parsed
    JSONL line). Always routes back through the dataclass's own
    __post_init__, so a hand-edited or corrupted line is caught here too,
    not only at original construction time.
    """
    if record_type not in FROM_DICT_BY_RECORD_TYPE:
        raise ValueError(f"unknown record_type {record_type!r}")
    return FROM_DICT_BY_RECORD_TYPE[record_type](data)
