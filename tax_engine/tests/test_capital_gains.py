"""Capital gains on disposal. CLAUDE.md Section 5.2 -- losses are never
silently netted; they're always flagged for accountant confirmation.
"""
from decimal import Decimal

from tax_engine.capital_gains import compute_capital_gains
from tax_engine.cost_basis import CostBasisPool


def test_gain_taxed_at_flat_rate(capital_gains_table):
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("5000.00"))
    disposal = pool.dispose(Decimal("1000"), proceeds_brl=Decimal("6000.00"))

    result = compute_capital_gains(disposal, capital_gains_table)

    assert result.regime == "foreign_no_exemption"
    assert result.monthly_exemption_applies is False
    # gain = 1000.00, rate 0.15 -> tax_due = 150.00
    assert result.tax_due == Decimal("150.00")
    assert result.loss_offset_flag == "not_applicable_gain"


def test_loss_is_never_taxed_and_always_flagged(capital_gains_table):
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("6000.00"))
    disposal = pool.dispose(Decimal("1000"), proceeds_brl=Decimal("5000.00"))

    result = compute_capital_gains(disposal, capital_gains_table)

    assert result.disposal.gain_or_loss_brl == Decimal("-1000.00")
    assert result.tax_due == Decimal("0.00")
    assert result.loss_offset_flag == "requires_accountant_confirmation"


def test_breakeven_disposal(capital_gains_table):
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("5000.00"))
    disposal = pool.dispose(Decimal("1000"), proceeds_brl=Decimal("5000.00"))

    result = compute_capital_gains(disposal, capital_gains_table)

    assert result.tax_due == Decimal("0.00")
    assert result.loss_offset_flag == "not_applicable_breakeven"


def test_table_provenance_surfaced_and_unverified(capital_gains_table):
    pool = CostBasisPool()
    pool.add_income(Decimal("100"), Decimal("500.00"))
    disposal = pool.dispose(Decimal("100"), proceeds_brl=Decimal("600.00"))

    result = compute_capital_gains(disposal, capital_gains_table)

    assert result.table_verified is False
    assert "Lei 14.754" in result.table_caveat or "planalto" in result.table_source_url
