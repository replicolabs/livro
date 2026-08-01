"""Dataclasses for cross-tenant billing/provisioning records.

Same discipline as ledger/records.py: frozen (append-only, never mutated),
self-validating in __post_init__, so an invalid record cannot be constructed
let alone written to disk. Reuses ledger.records's own arithmetic/timestamp
helpers rather than re-deriving them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ledger.records import _q, _require_datetime

TENANT_STATUSES = frozenset({"provisioning", "active", "suspended", "offboarded"})
TOPUP_SOURCES = frozenset({"onchain", "trial_grant"})


@dataclass(frozen=True)
class TenantRecord:
    """One per onboarded freelancer. `agent_alias` is the ZeroClaw
    `[agents.<agent_alias>]` this tenant is bound to -- by convention equal
    to `tenant_id`, kept as a separate field so a future re-key/migration
    has somewhere to diverge without renaming the tenant itself.
    """

    tenant_id: str
    wa_id: str
    agent_alias: str
    workspace_dir: str
    provisioned_at: datetime
    status: str = "provisioning"
    language: str = "pt-BR"

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.tenant_id.strip():
            raise ValueError("tenant_id must not be empty")
        if not self.wa_id or not self.wa_id.strip():
            raise ValueError("wa_id must not be empty")
        if self.status not in TENANT_STATUSES:
            raise ValueError(f"status {self.status!r} is not valid")
        _require_datetime(self.provisioned_at, "provisioned_at")


@dataclass(frozen=True)
class CreditTopUp:
    """Append-only. One per credited top-up -- either a real on-chain USDC
    payment to the owner's wallet, or a synthetic trial grant. `source`
    distinguishes them explicitly (following ExternalHolding's own
    `provenance` field precedent, ledger/records.py) rather than faking a
    transaction signature for a trial grant.
    """

    topup_id: str
    tenant_id: str
    reference_key: str
    usdc_amount: Decimal
    credited_usd_balance_delta: Decimal
    confirmed_at: datetime
    source: str
    tx_signature: Optional[str] = None

    def __post_init__(self) -> None:
        if self.source not in TOPUP_SOURCES:
            raise ValueError(f"source {self.source!r} is not valid")
        _require_datetime(self.confirmed_at, "confirmed_at")
        if self.credited_usd_balance_delta <= 0:
            raise ValueError("credited_usd_balance_delta must be positive")

        if self.source == "onchain":
            if not self.tx_signature or not self.tx_signature.strip():
                raise ValueError(
                    "source 'onchain' requires a real tx_signature -- never fabricate one"
                )
            if self.usdc_amount <= 0:
                raise ValueError("usdc_amount must be positive for an onchain top-up")
        else:  # trial_grant
            if self.tx_signature is not None:
                raise ValueError(
                    "source 'trial_grant' must not carry a tx_signature -- "
                    "there is no real transaction to point at, don't fake one"
                )
            if self.usdc_amount != 0:
                raise ValueError(
                    "usdc_amount must be exactly 0 for a trial_grant -- "
                    "no real USDC arrived; credited_usd_balance_delta alone carries the grant value"
                )


@dataclass(frozen=True)
class CreditDebit:
    """Append-only. One per reconciled turn cost, always pointing back at
    the exact costs.jsonl record it derives from -- CLAUDE.md Section 1.5's
    'every number has a receipt' principle, applied to platform billing.
    """

    debit_id: str
    tenant_id: str
    cost_record_ref: str
    usd_amount: Decimal
    debited_at: datetime

    def __post_init__(self) -> None:
        if not self.cost_record_ref or not self.cost_record_ref.strip():
            raise ValueError(
                "cost_record_ref must not be empty -- every debit must point back "
                "at the costs.jsonl record it was derived from"
            )
        if self.usd_amount <= 0:
            raise ValueError("usd_amount must be positive")
        _require_datetime(self.debited_at, "debited_at")


def compute_balance(topups: list[CreditTopUp], debits: list[CreditDebit]) -> Decimal:
    """TenantBalance is never a stored counter -- always derived by summing
    the append-only history, same chronological-derivation discipline as
    the existing cost-basis pool (tax_engine.cost_basis.CostBasisPool).
    """
    total_topups = sum((t.credited_usd_balance_delta for t in topups), Decimal("0"))
    total_debits = sum((d.usd_amount for d in debits), Decimal("0"))
    return _q(total_topups - total_debits)
