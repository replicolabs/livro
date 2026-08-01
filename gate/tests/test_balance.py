from datetime import datetime, timezone
from decimal import Decimal

from platform_ledger.records import CreditDebit, CreditTopUp

from gate.balance import (
    MIN_BALANCE_FLOOR,
    append_debit,
    append_topup,
    check_balance_gate,
    get_balance,
    load_debits,
    load_topups,
)

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_append_and_load_topup_round_trips(tmp_path):
    topup = CreditTopUp(
        topup_id="top_1",
        tenant_id="t_1",
        reference_key="trial",
        usdc_amount=Decimal("0"),
        credited_usd_balance_delta=Decimal("1.00"),
        confirmed_at=NOW,
        source="trial_grant",
    )
    append_topup(tmp_path, topup)

    loaded = load_topups(tmp_path, "t_1")
    assert len(loaded) == 1
    assert loaded[0].credited_usd_balance_delta == Decimal("1.00")
    assert loaded[0].tenant_id == "t_1"


def test_load_topups_filters_by_tenant(tmp_path):
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_1", tenant_id="t_1", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("1.00"),
        confirmed_at=NOW, source="trial_grant",
    ))
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_2", tenant_id="t_2", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("5.00"),
        confirmed_at=NOW, source="trial_grant",
    ))

    assert len(load_topups(tmp_path, "t_1")) == 1
    assert len(load_topups(tmp_path, "t_2")) == 1
    assert load_topups(tmp_path, "t_1")[0].credited_usd_balance_delta == Decimal("1.00")


def test_append_and_load_debit_round_trips(tmp_path):
    debit = CreditDebit(
        debit_id="d1", tenant_id="t_1", cost_record_ref="cost_1",
        usd_amount=Decimal("0.05"), debited_at=NOW,
    )
    append_debit(tmp_path, debit)

    loaded = load_debits(tmp_path, "t_1")
    assert len(loaded) == 1
    assert loaded[0].usd_amount == Decimal("0.05")


def test_get_balance_combines_topups_and_debits(tmp_path):
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_1", tenant_id="t_1", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("1.00"),
        confirmed_at=NOW, source="trial_grant",
    ))
    append_debit(tmp_path, CreditDebit(
        debit_id="d1", tenant_id="t_1", cost_record_ref="cost_1",
        usd_amount=Decimal("0.30"), debited_at=NOW,
    ))
    assert get_balance(tmp_path, "t_1") == Decimal("0.70")


def test_check_balance_gate_passes_when_above_floor(tmp_path):
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_1", tenant_id="t_1", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("1.00"),
        confirmed_at=NOW, source="trial_grant",
    ))
    assert check_balance_gate(tmp_path, "t_1") is True


def test_check_balance_gate_fails_below_floor(tmp_path):
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_1", tenant_id="t_1", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("0.10"),
        confirmed_at=NOW, source="trial_grant",
    ))
    append_debit(tmp_path, CreditDebit(
        debit_id="d1", tenant_id="t_1", cost_record_ref="cost_1",
        usd_amount=Decimal("1.00"), debited_at=NOW,
    ))
    # balance = 0.10 - 1.00 = -0.90, below the -0.50 floor
    assert check_balance_gate(tmp_path, "t_1") is False


def test_check_balance_gate_tolerates_small_negative_within_floor(tmp_path):
    append_topup(tmp_path, CreditTopUp(
        topup_id="top_1", tenant_id="t_1", reference_key="trial",
        usdc_amount=Decimal("0"), credited_usd_balance_delta=Decimal("0.10"),
        confirmed_at=NOW, source="trial_grant",
    ))
    append_debit(tmp_path, CreditDebit(
        debit_id="d1", tenant_id="t_1", cost_record_ref="cost_1",
        usd_amount=Decimal("0.30"), debited_at=NOW,
    ))
    # balance = 0.10 - 0.30 = -0.20, still above the -0.50 floor
    assert check_balance_gate(tmp_path, "t_1") is True


def test_new_tenant_with_no_history_is_at_zero_and_still_passes_the_floor(tmp_path):
    """A tenant with literally no topup history is at exactly zero, which
    is still above MIN_BALANCE_FLOOR (-0.50) -- in practice this shouldn't
    happen (provisioning always grants a trial credit first), but the gate
    itself correctly treats zero as passable, not as a hard "must be
    positive" requirement; the floor exists to tolerate post-hoc negative
    drift, not to block exact-zero starts.
    """
    assert get_balance(tmp_path, "t_never_topped_up") == Decimal("0.00")
    assert check_balance_gate(tmp_path, "t_never_topped_up") is True


def test_min_balance_floor_is_negative_not_zero():
    """Documents the deliberate tolerance policy from the plan -- a tenant
    isn't blocked the instant they hit exactly zero.
    """
    assert MIN_BALANCE_FLOOR == Decimal("-0.50")
