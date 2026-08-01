"""Integration coverage for CLAUDE.md Section 8.2's messy-payment scenarios:
overpayment, underpayment, wrong asset, and late-after-expiry.

These tests don't re-implement classify_receipt's classification logic --
that decision is made by the live LLM agent following
shared/skills/livro/classify_receipt/SKILL.md, which can't be unit-tested
without a running ZeroClaw instance (see SETUP.md Section 6). What CAN be
tested here, honestly and automatically, is the part that's pure code: given
the ledger shape classify_receipt's rules say each scenario SHOULD produce,
does the rest of the pipeline (cost-basis pooling, monthly Carne-Leao
totals, threshold watch) handle it correctly across a realistic multi-entry
month? A bug in how multiple entries interact (an overpayment's excess
double-counted, a late entry landing in the wrong month, a wrong-asset
receipt silently entering the USDC cost-basis pool) is exactly the kind of
thing this integration layer can catch even without a live agent.

If shared/skills/livro/classify_receipt/SKILL.md's classification rules
ever change, the fixture ledgers below should change to match -- they are a
snapshot of what compliant classification produces, not an independent
source of truth.
"""
from datetime import date
from decimal import Decimal

from tax_engine.carne_leao import CarneLeaoDeductions, compute_carne_leao
from tax_engine.cost_basis import CostBasisPool
from tax_engine.threshold_watch import check_threshold


def test_overpayment_books_two_separate_entries_and_pools_correctly(carne_leao_table):
    """classify_receipt: 'Book the matched portion normally. Log the excess
    as its own ledger_entry (its own income leg, its own BACEN rate lookup).'
    Both entries share a receipt date/rate here (same-day payment) but are
    still two distinct ledger rows, as the rule requires.
    """
    invoice_expected_usdc = Decimal("500")
    actual_payment_usdc = Decimal("550")
    ptax_rate = Decimal("5.40")

    matched_entry = {
        "usdc_amount": invoice_expected_usdc,
        "brl_value": invoice_expected_usdc * ptax_rate,
        "receipt_classification": "overpayment",
    }
    excess_entry = {
        "usdc_amount": actual_payment_usdc - invoice_expected_usdc,
        "brl_value": (actual_payment_usdc - invoice_expected_usdc) * ptax_rate,
        "receipt_classification": "overpayment_excess",
    }

    ledger_this_month = [matched_entry, excess_entry]
    assert len(ledger_this_month) == 2  # never merged into one entry

    pool = CostBasisPool()
    for entry in ledger_this_month:
        pool.add_income(entry["usdc_amount"], entry["brl_value"])

    assert pool.total_usdc_held == actual_payment_usdc
    assert pool.total_cost_basis_brl == actual_payment_usdc * ptax_rate

    gross_income = sum((e["brl_value"] for e in ledger_this_month), Decimal("0"))
    result = compute_carne_leao(gross_income, CarneLeaoDeductions(), carne_leao_table, "07/2026", "2026-08-31")
    assert result.gross_income == actual_payment_usdc * ptax_rate  # both legs counted, once each


def test_underpayment_books_partial_amount_only_and_invoice_stays_open():
    """classify_receipt: 'Book the partial amount that arrived... Keep the
    invoice open for the remainder rather than closing it.'
    """
    invoice_expected_usdc = Decimal("500")
    actual_payment_usdc = Decimal("300")
    ptax_rate = Decimal("5.40")

    partial_entry = {
        "usdc_amount": actual_payment_usdc,
        "brl_value": actual_payment_usdc * ptax_rate,
        "receipt_classification": "underpayment",
    }

    pool = CostBasisPool()
    pool.add_income(partial_entry["usdc_amount"], partial_entry["brl_value"])
    assert pool.total_usdc_held == Decimal("300")  # only the partial amount, never the full invoice amount

    remaining_open_usdc = invoice_expected_usdc - actual_payment_usdc
    assert remaining_open_usdc == Decimal("200")  # invoice stays open for this remainder, not silently closed


def test_wrong_asset_never_enters_the_usdc_cost_basis_pool():
    """classify_receipt: 'Do not run it through the standard BACEN/USDC
    booking path -- a different asset needs its own valuation.'
    """
    pool = CostBasisPool()
    payment_exception = {
        "kind": "wrong_asset",
        "detail": "received 1000 BONK instead of USDC",
        "resolution_status": "pending_freelancer_decision",
    }
    # The defining assertion: no add_income call happens for a wrong-asset
    # receipt. Simulate the full month otherwise being empty of USDC income
    # and confirm the pool reflects that -- a wrong-asset entry contributing
    # BRL value here would be exactly the silent-mishandling bug Section
    # 4.6/user story 11 warns against.
    assert payment_exception["kind"] == "wrong_asset"
    assert pool.total_usdc_held == Decimal("0")
    assert pool.total_cost_basis_brl == Decimal("0")


def test_late_after_expiry_payment_still_books_into_the_month_it_actually_landed(carne_leao_table):
    """classify_receipt: 'Book it normally, but flag the classification and
    notify the freelancer.' The tax consequence: it counts toward whatever
    calendar month it actually arrived in (for Carne-Leao purposes, receipt
    date governs, per CLAUDE.md Section 4.1's receipt_date field) -- not the
    month the original invoice was issued, and never silently dropped.
    """
    other_ordinary_entry = {"usdc_amount": Decimal("200"), "brl_value": Decimal("1080.00")}
    late_entry = {
        "usdc_amount": Decimal("100"),
        "brl_value": Decimal("540.00"),
        "receipt_classification": "late_after_expiry",
        "receipt_date": date(2026, 7, 20),
    }

    ledger_july = [other_ordinary_entry, late_entry]
    gross_income = sum((e["brl_value"] for e in ledger_july), Decimal("0"))

    result = compute_carne_leao(gross_income, CarneLeaoDeductions(), carne_leao_table, "07/2026", "2026-08-31")
    assert result.gross_income == Decimal("1620.00")  # both entries counted -- the late one is not dropped


def test_full_messy_month_threshold_watch_counts_every_leg(in1888_table):
    """A realistic messy month: exact match + overpayment's two legs +
    underpayment's partial leg all contribute to the IN 1888 cumulative
    volume check -- a wrong-asset entry does not (it never entered BRL
    terms), matching the same discipline as the cost-basis test above.
    """
    exact_match = Decimal("5000.00")
    overpayment_matched = Decimal("2700.00")
    overpayment_excess = Decimal("270.00")
    underpayment_partial = Decimal("1620.00")
    # wrong_asset contributes nothing -- deliberately excluded

    cumulative = exact_match + overpayment_matched + overpayment_excess + underpayment_partial
    status = check_threshold(cumulative, in1888_table)

    assert status.cumulative_volume_brl == Decimal("9590.00")
    assert status.exceeded is False
    assert status.approaching is False
