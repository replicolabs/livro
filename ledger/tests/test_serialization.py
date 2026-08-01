"""Round-trip: construct -> to_json_line -> parse -> from_dict -> equal
record. A corrupted/hand-edited JSONL line must fail the same validation as
original construction, not be trusted blindly on read.
"""
import json
from datetime import datetime
from decimal import Decimal

import pytest

from ledger.records import DispositionInstruction, FxRateUsed, IncomeEntry
from ledger.serialization import (
    disposition_instruction_from_dict,
    from_dict,
    income_entry_from_dict,
    to_json_line,
)

NOW = datetime(2026, 7, 30, 12, 0, 0)
FX = FxRateUsed(
    source="BCB PTAX",
    endpoint_queried="https://olinda.bcb.gov.br/...",
    quote_type="venda",
    date_of_quote=NOW.date(),
    fallback_rule_applied=False,
)


def test_income_entry_round_trips_through_json():
    entry = IncomeEntry(
        entry_id="e1",
        tx_signature="sig1",
        reference_key="ref1",
        receiving_address="addr1",
        client_label="Berlin client",
        usdc_amount=Decimal("500"),
        receipt_date=NOW.date(),
        receipt_classification="exact_match",
        expected_amount=Decimal("500"),
        fx_rate=Decimal("5.40"),
        fx_rate_used=FX,
        brl_value=Decimal("2700.00"),
        created_at=NOW,
    )
    line = to_json_line(entry)
    parsed = json.loads(line)
    restored = income_entry_from_dict(parsed)

    assert restored == entry
    assert isinstance(restored.brl_value, Decimal)
    assert isinstance(restored.receipt_date, type(NOW.date()))


def test_disposition_instruction_round_trips():
    instruction = DispositionInstruction(
        entry_id="d1",
        linked_income_entry_id="e1",
        instruction_source="explicit_per_payment",
        instruction="convert_to_brl",
        confirmed_by_user_at=NOW,
    )
    restored = disposition_instruction_from_dict(json.loads(to_json_line(instruction)))
    assert restored == instruction


def test_corrupted_jsonl_line_fails_the_same_validation_on_read():
    """A hand-edited or corrupted line with a null confirmation timestamp
    must not silently load -- from_dict re-runs __post_init__.
    """
    corrupted = {
        "entry_id": "d1",
        "linked_income_entry_id": "e1",
        "instruction_source": "explicit_per_payment",
        "instruction": "convert_to_brl",
        "confirmed_by_user_at": None,
    }
    with pytest.raises(ValueError, match="must not be null"):
        disposition_instruction_from_dict(corrupted)


def test_from_dict_dispatches_by_record_type():
    instruction_dict = {
        "entry_id": "d1",
        "linked_income_entry_id": "e1",
        "instruction_source": "explicit_per_payment",
        "instruction": "hold_as_usdc",
        "confirmed_by_user_at": NOW.isoformat(),
    }
    restored = from_dict("disposition_instruction", instruction_dict)
    assert restored.instruction == "hold_as_usdc"


def test_from_dict_rejects_unknown_record_type():
    with pytest.raises(ValueError, match="unknown record_type"):
        from_dict("not_a_real_type", {})
