"""CLAUDE.md Section 7: 'the code should make it structurally awkward to
create one of these records without that field populated' -- these tests
prove the awkwardness actually exists (construction raises), not just that
happy-path construction works.
"""
from datetime import datetime
from decimal import Decimal

import pytest

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

NOW = datetime(2026, 7, 30, 12, 0, 0)
FX = FxRateUsed(
    source="BCB PTAX",
    endpoint_queried="https://olinda.bcb.gov.br/...",
    quote_type="venda",
    date_of_quote=NOW.date(),
    fallback_rule_applied=False,
)


def _income_entry(**overrides):
    defaults = dict(
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
    defaults.update(overrides)
    return IncomeEntry(**defaults)


# ── IncomeEntry ──────────────────────────────────────────────────────────

def test_income_entry_valid_construction_succeeds():
    entry = _income_entry()
    assert entry.brl_value == Decimal("2700.00")


def test_income_entry_rejects_mismatched_brl_value():
    with pytest.raises(ValueError, match="derivation"):
        _income_entry(brl_value=Decimal("9999.99"))


def test_income_entry_rejects_invalid_classification():
    with pytest.raises(ValueError):
        _income_entry(receipt_classification="not_a_real_classification")


def test_income_entry_rejects_non_positive_usdc_amount():
    with pytest.raises(ValueError):
        _income_entry(usdc_amount=Decimal("0"))


# ── DispositionInstruction ──────────────────────────────────────────────

def test_disposition_instruction_rejects_null_confirmation():
    with pytest.raises(ValueError, match="must not be null"):
        DispositionInstruction(
            entry_id="d1",
            linked_income_entry_id="e1",
            instruction_source="explicit_per_payment",
            instruction="convert_to_brl",
            confirmed_by_user_at=None,
        )


def test_disposition_instruction_rejects_string_placeholder_for_timestamp():
    """A common LLM failure mode: writing a string like 'pending' or
    'null' instead of an actual timestamp. Must be caught, not silently
    accepted as truthy.
    """
    with pytest.raises(TypeError):
        DispositionInstruction(
            entry_id="d1",
            linked_income_entry_id="e1",
            instruction_source="explicit_per_payment",
            instruction="convert_to_brl",
            confirmed_by_user_at="2026-07-30T12:00:00",  # a string, not a datetime
        )


def test_disposition_instruction_valid_construction_succeeds():
    d = DispositionInstruction(
        entry_id="d1",
        linked_income_entry_id="e1",
        instruction_source="explicit_per_payment",
        instruction="hold_as_usdc",
        confirmed_by_user_at=NOW,
    )
    assert d.confirmed_by_user_at == NOW


def test_disposition_instruction_allocate_bond_requires_allocation_details():
    with pytest.raises(ValueError, match="allocation_details"):
        DispositionInstruction(
            entry_id="d1",
            linked_income_entry_id="e1",
            instruction_source="explicit_per_payment",
            instruction="allocate_bond",
            confirmed_by_user_at=NOW,
            allocation_details=None,
        )


def test_disposition_instruction_non_bond_instruction_rejects_allocation_details():
    with pytest.raises(ValueError):
        DispositionInstruction(
            entry_id="d1",
            linked_income_entry_id="e1",
            instruction_source="explicit_per_payment",
            instruction="hold_as_usdc",
            confirmed_by_user_at=NOW,
            allocation_details={"amount": "100"},
        )


# ── DisposalEntry ────────────────────────────────────────────────────────

def test_disposal_entry_rejects_mismatched_gain_loss():
    with pytest.raises(ValueError, match="derivation"):
        DisposalEntry(
            entry_id="disp1",
            linked_income_entry_ids=("e1",),
            disposal_date=NOW.date(),
            disposal_reason="converted_to_brl",
            usdc_amount_disposed=Decimal("100"),
            cost_basis_brl=Decimal("500.00"),
            proceeds_brl=Decimal("550.00"),
            gain_or_loss_brl=Decimal("999.99"),  # should be 50.00
            regime_applied="foreign_no_exemption",
            created_at=NOW,
        )


def test_disposal_entry_requires_at_least_one_linked_income_entry():
    with pytest.raises(ValueError, match="at least one"):
        DisposalEntry(
            entry_id="disp1",
            linked_income_entry_ids=(),
            disposal_date=NOW.date(),
            disposal_reason="spent",
            usdc_amount_disposed=Decimal("100"),
            cost_basis_brl=Decimal("500.00"),
            proceeds_brl=Decimal("550.00"),
            gain_or_loss_brl=Decimal("50.00"),
            regime_applied="foreign_no_exemption",
            created_at=NOW,
        )


# ── BondPosition ─────────────────────────────────────────────────────────

def test_bond_position_rejects_non_placeholder_tax_treatment_flag():
    with pytest.raises(ValueError, match="novel_asset_class_unresolved"):
        BondPosition(
            position_id="b1",
            linked_disposal_entry_id="disp1",
            bond="TESOURO",
            provider="Etherfuse",
            amount_allocated_usdc_equivalent=Decimal("100"),
            draft_tx="unsigned-tx-blob",
            tax_treatment_flag="confidently_resolved",  # never allowed for v1
        )


def test_bond_position_rejects_empty_draft_tx():
    with pytest.raises(ValueError, match="draft_tx"):
        BondPosition(
            position_id="b1",
            linked_disposal_entry_id="disp1",
            bond="TESOURO",
            provider="Etherfuse",
            amount_allocated_usdc_equivalent=Decimal("100"),
            draft_tx="",
        )


def test_bond_position_valid_construction_succeeds():
    b = BondPosition(
        position_id="b1",
        linked_disposal_entry_id="disp1",
        bond="TESOURO",
        provider="Etherfuse",
        amount_allocated_usdc_equivalent=Decimal("100"),
        draft_tx="unsigned-tx-blob",
    )
    assert b.tax_treatment_flag == "novel_asset_class_unresolved"


# ── PaymentException ─────────────────────────────────────────────────────

def test_payment_exception_resolved_requires_resolution_and_timestamp():
    with pytest.raises(ValueError, match="resolved"):
        PaymentException(
            exception_id="pe1",
            linked_income_entry_id="e1",
            kind="overpayment",
            detail="R$50 excess",
            resolution_status="resolved",
            resolution=None,
            resolved_at=None,
        )


def test_payment_exception_pending_rejects_premature_resolution_fields():
    with pytest.raises(ValueError):
        PaymentException(
            exception_id="pe1",
            linked_income_entry_id="e1",
            kind="overpayment",
            detail="R$50 excess",
            resolution_status="pending_freelancer_decision",
            resolution="applied_to_next_invoice",  # should not be set yet
            resolved_at=None,
        )


# ── RefundDraft ──────────────────────────────────────────────────────────

def test_refund_draft_rejects_empty_destination_address():
    with pytest.raises(ValueError, match="destination_address"):
        RefundDraft(
            draft_id="r1",
            linked_income_entry_id="e1",
            destination_address="",
            amount_usdc=Decimal("50"),
            confirmed_by_freelancer_at=NOW,
            draft_tx="unsigned-tx-blob",
        )


def test_refund_draft_rejects_null_confirmation():
    with pytest.raises(ValueError, match="must not be null"):
        RefundDraft(
            draft_id="r1",
            linked_income_entry_id="e1",
            destination_address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            amount_usdc=Decimal("50"),
            confirmed_by_freelancer_at=None,
            draft_tx="unsigned-tx-blob",
        )


def test_refund_draft_valid_construction_succeeds():
    r = RefundDraft(
        draft_id="r1",
        linked_income_entry_id="e1",
        destination_address="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        amount_usdc=Decimal("50"),
        confirmed_by_freelancer_at=NOW,
        draft_tx="unsigned-tx-blob",
    )
    assert r.status == "drafted"


# ── ExternalHolding ──────────────────────────────────────────────────────

def test_external_holding_rejects_wrong_provenance():
    with pytest.raises(ValueError, match="provenance"):
        ExternalHolding(
            holding_id="h1",
            declared_by_user_at=NOW,
            asset="USDC",
            amount=Decimal("100"),
            approx_receipt_date=NOW.date(),
            rate_used=Decimal("5.40"),
            brl_value=Decimal("540.00"),
            provenance="observed_onchain",  # only declared_by_user is ever valid here
        )


def test_external_holding_rejects_mismatched_brl_value():
    with pytest.raises(ValueError, match="derivation"):
        ExternalHolding(
            holding_id="h1",
            declared_by_user_at=NOW,
            asset="USDC",
            amount=Decimal("100"),
            approx_receipt_date=NOW.date(),
            rate_used=Decimal("5.40"),
            brl_value=Decimal("1.00"),
        )


# ── Records are frozen (append-only, never mutated) ──────────────────────

def test_records_are_immutable():
    entry = _income_entry()
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError, a subclass of AttributeError
        entry.brl_value = Decimal("1.00")
