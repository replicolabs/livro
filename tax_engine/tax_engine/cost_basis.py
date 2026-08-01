"""Weighted-average cost basis pool. CLAUDE.md Section 5.3.

Deliberately the smallest, most heavily tested module in the engine per
Section 5.3's own warning: "Test this arithmetic exhaustively -- it's the
part most likely to have a subtle bug that silently produces wrong tax
figures."
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class CostBasisPool:
    """Mutable running (total_usdc_held, total_cost_basis_brl) pair for one user.

    Both directly-observed and externally-declared (Section 4.8) entries feed
    the same pool; `provenance` is carried on the caller's ledger entry, not
    inside the pool itself, since the pool only needs the aggregate numbers.
    """

    total_usdc_held: Decimal = Decimal("0")
    total_cost_basis_brl: Decimal = Decimal("0")

    def add_income(self, usdc_amount: Decimal, brl_value: Decimal) -> None:
        if usdc_amount < 0:
            raise ValueError("usdc_amount must be non-negative for an income entry")
        self.total_usdc_held += usdc_amount
        self.total_cost_basis_brl += brl_value

    def dispose(self, usdc_amount: Decimal, proceeds_brl: Decimal) -> "DisposalResult":
        """Draw down `usdc_amount` USDC from the pool at the disposal's proceeds.

        Raises ValueError if the pool holds less than usdc_amount -- disposing
        more than is held is a data-integrity error the caller must fix
        upstream, not something to silently clamp.
        """
        if usdc_amount <= 0:
            raise ValueError("usdc_amount must be positive for a disposal")
        if usdc_amount > self.total_usdc_held:
            raise ValueError(
                f"cannot dispose {usdc_amount} USDC; pool only holds {self.total_usdc_held}"
            )

        proportion = usdc_amount / self.total_usdc_held
        cost_basis_for_disposal = _q(proportion * self.total_cost_basis_brl)
        gain_or_loss = _q(proceeds_brl - cost_basis_for_disposal)

        self.total_usdc_held -= usdc_amount
        self.total_cost_basis_brl -= cost_basis_for_disposal

        # Full disposal: zero out residual cent-level drift rather than leave
        # a near-zero non-zero balance from repeated Decimal division.
        if self.total_usdc_held == 0:
            self.total_cost_basis_brl = Decimal("0")

        return DisposalResult(
            usdc_amount_disposed=usdc_amount,
            cost_basis_brl=cost_basis_for_disposal,
            proceeds_brl=_q(proceeds_brl),
            gain_or_loss_brl=gain_or_loss,
            remaining_usdc_held=self.total_usdc_held,
            remaining_cost_basis_brl=self.total_cost_basis_brl,
        )


@dataclass(frozen=True)
class DisposalResult:
    usdc_amount_disposed: Decimal
    cost_basis_brl: Decimal
    proceeds_brl: Decimal
    gain_or_loss_brl: Decimal
    remaining_usdc_held: Decimal
    remaining_cost_basis_brl: Decimal
