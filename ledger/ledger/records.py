"""Dataclasses for every append-only ledger record type. CLAUDE.md Section 4.

Every dataclass is frozen (immutable once constructed -- matches "append
only, never edit") and validates itself in `__post_init__`. A record that
fails validation raises immediately at construction time; there is no way
to hold an invalid record in memory, let alone serialize one to the ledger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

TWO_PLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _require_datetime(value, field_name: str) -> None:
    """CLAUDE.md's own words for disposition_instruction: 'If
    confirmed_by_user_at would be null, the code path is wrong -- this
    record must not be created until confirmation exists.' Generalized to
    every confirmation-timestamp field across every record type.
    """
    if value is None:
        raise ValueError(
            f"{field_name} must not be null -- this record must not be constructed "
            "until real confirmation exists (CLAUDE.md Section 4.2/4.7/7)"
        )
    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be an actual datetime instance, not {type(value).__name__} "
            "-- a string placeholder or sentinel value defeats the point of this check"
        )


def _require_derivation(actual: Decimal, expected: Decimal, description: str) -> None:
    """CLAUDE.md Section 1.5: 'Every number has a receipt... No number
    should ever exist in the ledger without its derivation attached.'
    Enforced here as an arithmetic identity check, not just a docs promise.
    """
    if _q(actual) != _q(expected):
        raise ValueError(
            f"{description}: stated value {_q(actual)} does not match its derivation "
            f"{_q(expected)} -- every ledger figure must be traceable to its inputs "
            "(CLAUDE.md Section 1.5)"
        )


RECEIPT_CLASSIFICATIONS = frozenset(
    {"exact_match", "overpayment", "underpayment", "wrong_asset", "late_after_expiry"}
)
DISPOSITION_INSTRUCTIONS = frozenset({"convert_to_brl", "hold_as_usdc", "allocate_bond"})
DISPOSITION_SOURCES = frozenset({"standing_preference", "explicit_per_payment"})
DISPOSAL_REASONS = frozenset({"converted_to_brl", "spent", "allocated_to_bond"})
DRAFT_STATUSES = frozenset({"drafted", "user_confirmed_signed", "abandoned"})
EXCEPTION_KINDS = frozenset({"overpayment", "underpayment", "wrong_asset", "late_after_expiry"})
EXCEPTION_RESOLUTION_STATUSES = frozenset({"pending_freelancer_decision", "resolved"})


@dataclass(frozen=True)
class FxRateUsed:
    source: str
    endpoint_queried: str
    quote_type: str
    date_of_quote: date
    fallback_rule_applied: bool


@dataclass(frozen=True)
class IncomeEntry:
    """CLAUDE.md Section 4.1 -- one per payment, income leg."""

    entry_id: str
    tx_signature: str
    reference_key: str
    receiving_address: str
    client_label: str
    usdc_amount: Decimal
    receipt_date: date
    receipt_classification: str
    expected_amount: Decimal
    fx_rate: Decimal
    fx_rate_used: FxRateUsed
    brl_value: Decimal
    created_at: datetime
    notes: str = ""

    def __post_init__(self) -> None:
        if self.receipt_classification not in RECEIPT_CLASSIFICATIONS:
            raise ValueError(f"receipt_classification {self.receipt_classification!r} is not valid")
        if self.usdc_amount <= 0:
            raise ValueError("usdc_amount must be positive")
        if self.fx_rate <= 0:
            raise ValueError("fx_rate must be positive")
        _require_derivation(self.brl_value, self.usdc_amount * self.fx_rate, "brl_value")


@dataclass(frozen=True)
class DispositionInstruction:
    """CLAUDE.md Section 4.2 -- captures explicit user intent, one per payment."""

    entry_id: str
    linked_income_entry_id: str
    instruction_source: str
    instruction: str
    confirmed_by_user_at: datetime
    allocation_details: Optional[dict] = None

    def __post_init__(self) -> None:
        if self.instruction_source not in DISPOSITION_SOURCES:
            raise ValueError(f"instruction_source {self.instruction_source!r} is not valid")
        if self.instruction not in DISPOSITION_INSTRUCTIONS:
            raise ValueError(f"instruction {self.instruction!r} is not valid")
        _require_datetime(self.confirmed_by_user_at, "confirmed_by_user_at")
        if self.instruction == "allocate_bond" and not self.allocation_details:
            raise ValueError(
                "instruction 'allocate_bond' requires allocation_details naming amount and "
                "target bond -- CLAUDE.md Section 4.2: 'only populated after user explicitly names it'"
            )
        if self.instruction != "allocate_bond" and self.allocation_details:
            raise ValueError("allocation_details must be null unless instruction is 'allocate_bond'")


@dataclass(frozen=True)
class DisposalEntry:
    """CLAUDE.md Section 4.3 -- disposal leg, created whenever USDC converts/spends/allocates."""

    entry_id: str
    linked_income_entry_ids: tuple[str, ...]
    disposal_date: date
    disposal_reason: str
    usdc_amount_disposed: Decimal
    cost_basis_brl: Decimal
    proceeds_brl: Decimal
    gain_or_loss_brl: Decimal
    regime_applied: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.disposal_reason not in DISPOSAL_REASONS:
            raise ValueError(f"disposal_reason {self.disposal_reason!r} is not valid")
        if not self.linked_income_entry_ids:
            raise ValueError("a disposal must link at least one income entry")
        if self.usdc_amount_disposed <= 0:
            raise ValueError("usdc_amount_disposed must be positive")
        _require_derivation(
            self.gain_or_loss_brl, self.proceeds_brl - self.cost_basis_brl, "gain_or_loss_brl"
        )


@dataclass(frozen=True)
class BondPosition:
    """CLAUDE.md Section 4.4 -- only if allocation feature used."""

    position_id: str
    linked_disposal_entry_id: str
    bond: str
    provider: str
    amount_allocated_usdc_equivalent: Decimal
    draft_tx: str
    status: str = "drafted"
    tax_treatment_flag: str = "novel_asset_class_unresolved"

    def __post_init__(self) -> None:
        if self.status not in DRAFT_STATUSES:
            raise ValueError(f"status {self.status!r} is not valid")
        if self.tax_treatment_flag != "novel_asset_class_unresolved":
            raise ValueError(
                "tax_treatment_flag must always be 'novel_asset_class_unresolved' for v1 -- "
                "CLAUDE.md Section 4.4: never compute a confident yield tax figure"
            )
        if not self.draft_tx or not self.draft_tx.strip():
            raise ValueError("draft_tx must not be empty -- never a signed tx, but never absent either")
        if self.amount_allocated_usdc_equivalent <= 0:
            raise ValueError("amount_allocated_usdc_equivalent must be positive")


@dataclass(frozen=True)
class PaymentException:
    """CLAUDE.md Section 4.6 -- created whenever receipt_classification isn't exact_match."""

    exception_id: str
    linked_income_entry_id: str
    kind: str
    detail: str
    resolution_status: str = "pending_freelancer_decision"
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.kind not in EXCEPTION_KINDS:
            raise ValueError(f"kind {self.kind!r} is not valid")
        if self.resolution_status not in EXCEPTION_RESOLUTION_STATUSES:
            raise ValueError(f"resolution_status {self.resolution_status!r} is not valid")
        if self.resolution_status == "resolved":
            if self.resolution is None or self.resolved_at is None:
                raise ValueError(
                    "resolution_status 'resolved' requires both resolution and resolved_at populated"
                )
        else:
            if self.resolution is not None or self.resolved_at is not None:
                raise ValueError(
                    "resolution and resolved_at must stay null while "
                    "resolution_status is 'pending_freelancer_decision'"
                )


@dataclass(frozen=True)
class RefundDraft:
    """CLAUDE.md Section 4.7 -- only created on explicit freelancer request."""

    draft_id: str
    linked_income_entry_id: str
    destination_address: str
    amount_usdc: Decimal
    confirmed_by_freelancer_at: datetime
    draft_tx: str
    status: str = "drafted"

    def __post_init__(self) -> None:
        if not self.destination_address or not self.destination_address.strip():
            raise ValueError(
                "destination_address must be explicitly provided -- never auto-filled from "
                "the paying wallet (CLAUDE.md Section 4.7)"
            )
        _require_datetime(self.confirmed_by_freelancer_at, "confirmed_by_freelancer_at")
        if self.amount_usdc <= 0:
            raise ValueError("amount_usdc must be positive")
        if self.status not in DRAFT_STATUSES:
            raise ValueError(f"status {self.status!r} is not valid")
        if not self.draft_tx or not self.draft_tx.strip():
            raise ValueError("draft_tx must not be empty -- Livro never signs, but must hand back a real draft")


@dataclass(frozen=True)
class ExternalHolding:
    """CLAUDE.md Section 4.8 -- optional, freelancer-declared, not directly observed."""

    holding_id: str
    declared_by_user_at: datetime
    asset: str
    amount: Decimal
    approx_receipt_date: date
    rate_used: Decimal
    brl_value: Decimal
    provenance: str = "declared_by_user"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.provenance != "declared_by_user":
            raise ValueError("provenance must always be 'declared_by_user' for this record type")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.rate_used <= 0:
            raise ValueError("rate_used must be positive")
        _require_derivation(self.brl_value, self.amount * self.rate_used, "brl_value")
