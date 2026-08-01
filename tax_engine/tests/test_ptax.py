"""BACEN PTAX weekend/holiday fallback. CLAUDE.md Section 6.1 / 8.1.

quote_lookup stands in for the real Olinda API call (mocked, no live network,
per CLAUDE.md Section 8.2).
"""
from datetime import date
from decimal import Decimal

import pytest

from tax_engine.ptax import NoPtaxQuoteFoundError, resolve_ptax_rate


def _fixed_lookup(quotes: dict):
    def lookup(d: date):
        return quotes.get(d)
    return lookup


def test_rate_published_on_receipt_date_needs_no_fallback():
    quotes = {date(2026, 7, 15): Decimal("5.4321")}
    result = resolve_ptax_rate(date(2026, 7, 15), _fixed_lookup(quotes))

    assert result.date_used == date(2026, 7, 15)
    assert result.rate == Decimal("5.4321")
    assert result.fallback_rule_applied is False


def test_weekend_falls_back_to_most_recent_prior_business_day():
    # 2026-07-18 is a Saturday; Friday 2026-07-17 has the last published quote.
    quotes = {date(2026, 7, 17): Decimal("5.5000")}
    result = resolve_ptax_rate(date(2026, 7, 18), _fixed_lookup(quotes))

    assert result.date_used == date(2026, 7, 17)
    assert result.rate == Decimal("5.5000")
    assert result.fallback_rule_applied is True
    assert result.requested_date == date(2026, 7, 18)


def test_holiday_gap_of_several_days_falls_back_correctly():
    # A multi-day holiday gap (e.g. a long weekend); only 2026-07-10 published.
    quotes = {date(2026, 7, 10): Decimal("5.4000")}
    result = resolve_ptax_rate(date(2026, 7, 13), _fixed_lookup(quotes))

    assert result.date_used == date(2026, 7, 10)
    assert result.fallback_rule_applied is True


def test_no_quote_within_lookback_window_raises():
    quotes = {}
    with pytest.raises(NoPtaxQuoteFoundError):
        resolve_ptax_rate(date(2026, 7, 18), _fixed_lookup(quotes), max_lookback_days=5)


def test_quote_type_is_recorded():
    quotes = {date(2026, 7, 15): Decimal("5.4321")}
    result = resolve_ptax_rate(date(2026, 7, 15), _fixed_lookup(quotes), quote_type="compra")
    assert result.quote_type == "compra"
