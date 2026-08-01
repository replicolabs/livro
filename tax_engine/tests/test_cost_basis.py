"""Weighted-average cost basis, exhaustively tested per CLAUDE.md Section 5.3's
own warning that this arithmetic is the most likely place for a silent bug.
"""
from decimal import Decimal

import pytest

from tax_engine.cost_basis import CostBasisPool


def test_single_income_then_full_disposal():
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("5000.00"))  # rate 5.00 BRL/USDC

    result = pool.dispose(Decimal("1000"), proceeds_brl=Decimal("5500.00"))

    assert result.cost_basis_brl == Decimal("5000.00")
    assert result.gain_or_loss_brl == Decimal("500.00")
    assert result.remaining_usdc_held == Decimal("0")
    assert result.remaining_cost_basis_brl == Decimal("0")


def test_weighted_average_across_multiple_income_entries_then_partial_disposal():
    pool = CostBasisPool()
    # 1000 USDC @ 5.00 BRL = 5000.00
    pool.add_income(Decimal("1000"), Decimal("5000.00"))
    # 500 USDC @ 6.00 BRL = 3000.00
    pool.add_income(Decimal("500"), Decimal("3000.00"))
    # pool: 1500 USDC held, 8000.00 BRL cost basis -> weighted avg 5.3333.../USDC

    # Dispose 600 USDC (40% of the pool) at 5.50 BRL/USDC proceeds = 3300.00
    result = pool.dispose(Decimal("600"), proceeds_brl=Decimal("3300.00"))

    # cost_basis_for_disposal = (600/1500) * 8000.00 = 3200.00
    assert result.cost_basis_brl == Decimal("3200.00")
    assert result.gain_or_loss_brl == Decimal("100.00")

    # remaining pool: 900 USDC, 8000.00 - 3200.00 = 4800.00 cost basis
    assert result.remaining_usdc_held == Decimal("900")
    assert result.remaining_cost_basis_brl == Decimal("4800.00")
    assert pool.total_usdc_held == Decimal("900")
    assert pool.total_cost_basis_brl == Decimal("4800.00")


def test_sequential_partial_disposals_reduce_running_totals_correctly():
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("4000.00"))  # 4.00 BRL/USDC

    first = pool.dispose(Decimal("300"), proceeds_brl=Decimal("1350.00"))
    assert first.cost_basis_brl == Decimal("1200.00")  # 300/1000 * 4000
    assert first.gain_or_loss_brl == Decimal("150.00")
    assert pool.total_usdc_held == Decimal("700")
    assert pool.total_cost_basis_brl == Decimal("2800.00")

    # New income arrives at a different rate before the second disposal.
    pool.add_income(Decimal("300"), Decimal("1800.00"))  # 6.00 BRL/USDC
    # pool now: 1000 USDC, 4600.00 BRL cost basis

    second = pool.dispose(Decimal("500"), proceeds_brl=Decimal("2000.00"))
    # cost_basis_for_disposal = (500/1000) * 4600.00 = 2300.00
    assert second.cost_basis_brl == Decimal("2300.00")
    assert second.gain_or_loss_brl == Decimal("-300.00")  # a loss
    assert pool.total_usdc_held == Decimal("500")
    assert pool.total_cost_basis_brl == Decimal("2300.00")


def test_loss_on_disposal():
    pool = CostBasisPool()
    pool.add_income(Decimal("1000"), Decimal("6000.00"))

    result = pool.dispose(Decimal("1000"), proceeds_brl=Decimal("5000.00"))
    assert result.gain_or_loss_brl == Decimal("-1000.00")


def test_cannot_dispose_more_than_held():
    pool = CostBasisPool()
    pool.add_income(Decimal("100"), Decimal("500.00"))

    with pytest.raises(ValueError):
        pool.dispose(Decimal("101"), proceeds_brl=Decimal("510.00"))


def test_cannot_add_negative_income():
    pool = CostBasisPool()
    with pytest.raises(ValueError):
        pool.add_income(Decimal("-100"), Decimal("-500.00"))


def test_cannot_dispose_non_positive_amount():
    pool = CostBasisPool()
    pool.add_income(Decimal("100"), Decimal("500.00"))
    with pytest.raises(ValueError):
        pool.dispose(Decimal("0"), proceeds_brl=Decimal("0"))
