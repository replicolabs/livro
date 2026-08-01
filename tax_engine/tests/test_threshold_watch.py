"""IN 1888 / DeCripto self-report threshold. CLAUDE.md Section 5.5 --
must flag approaching the threshold at the right point, not before, not after.
"""
from decimal import Decimal

from tax_engine.threshold_watch import check_threshold


def test_well_below_threshold_no_flag(in1888_table):
    status = check_threshold(Decimal("1000"), in1888_table)
    assert status.approaching is False
    assert status.exceeded is False


def test_just_under_80_percent_does_not_flag_approaching(in1888_table):
    threshold = Decimal(str(in1888_table["monthly_threshold_brl"]))
    just_under = threshold * Decimal("0.79")
    status = check_threshold(just_under, in1888_table)
    assert status.approaching is False
    assert status.exceeded is False


def test_at_80_percent_flags_approaching(in1888_table):
    threshold = Decimal(str(in1888_table["monthly_threshold_brl"]))
    at_80 = threshold * Decimal("0.8")
    status = check_threshold(at_80, in1888_table)
    assert status.approaching is True
    assert status.exceeded is False


def test_at_exactly_threshold_is_exceeded_not_just_approaching(in1888_table):
    threshold = Decimal(str(in1888_table["monthly_threshold_brl"]))
    status = check_threshold(threshold, in1888_table)
    assert status.exceeded is True
    assert status.approaching is False


def test_above_threshold_is_exceeded(in1888_table):
    threshold = Decimal(str(in1888_table["monthly_threshold_brl"]))
    status = check_threshold(threshold * 2, in1888_table)
    assert status.exceeded is True


def test_table_provenance_surfaced(in1888_table):
    status = check_threshold(Decimal("1000"), in1888_table)
    assert status.table_verified is False
    assert status.threshold_brl == Decimal("35000.00")
