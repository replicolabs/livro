"""Capital gains tax on disposal. CLAUDE.md Section 5.2.

Applies the dated capital-gains table's flat rate to a cost_basis.DisposalResult.
Deliberately does NOT net a loss against other gains -- Section 5.2 requires
losses be flagged for accountant confirmation rather than silently offset.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from tax_engine.cost_basis import DisposalResult

TWO_PLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CapitalGainsResult:
    disposal: DisposalResult
    regime: str
    rate: Decimal
    tax_due: Decimal
    monthly_exemption_applies: bool
    loss_offset_flag: str
    table_effective_from: str
    table_source_url: str
    table_verified: bool
    table_caveat: str


def compute_capital_gains(disposal: DisposalResult, table: dict) -> CapitalGainsResult:
    """Compute the tax due on one disposal under the foreign/self-custody regime.

    table must declare monthly_exemption_applies = false for this regime
    (Section 5.2: no small-transaction monthly exemption for foreign-counterparty,
    self-custody receipts, per research pending IN 1888 primary-source confirmation).
    A gain is taxed at `rate`; a loss is never netted here and is always flagged
    for accountant confirmation rather than assumed offsettable.
    """
    regime = table["regime"]
    rate = Decimal(str(table["rate"]))
    monthly_exemption_applies = bool(table["monthly_exemption_applies"])

    if disposal.gain_or_loss_brl > 0:
        tax_due = _q(disposal.gain_or_loss_brl * rate)
        loss_offset_flag = "not_applicable_gain"
    elif disposal.gain_or_loss_brl == 0:
        tax_due = Decimal("0.00")
        loss_offset_flag = "not_applicable_breakeven"
    else:
        tax_due = Decimal("0.00")
        loss_offset_flag = "requires_accountant_confirmation"

    return CapitalGainsResult(
        disposal=disposal,
        regime=regime,
        rate=rate,
        tax_due=tax_due,
        monthly_exemption_applies=monthly_exemption_applies,
        loss_offset_flag=loss_offset_flag,
        table_effective_from=table["effective_from"],
        table_source_url=table["source_url"],
        table_verified=bool(table.get("verified", False)),
        table_caveat=table.get("verification_caveat", ""),
    )
