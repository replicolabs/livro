from datetime import datetime
from decimal import Decimal

import pytest

from platform_ledger.records import (
    CreditDebit,
    CreditTopUp,
    TenantRecord,
    compute_balance,
)

NOW = datetime(2026, 8, 1, 12, 0, 0)


# ── TenantRecord ─────────────────────────────────────────────────────────

def test_tenant_record_valid_construction():
    t = TenantRecord(
        tenant_id="t_abc123",
        wa_id="5511999999999",
        agent_alias="t_abc123",
        workspace_dir="/data/agents/t_abc123/workspace",
        provisioned_at=NOW,
    )
    assert t.status == "provisioning"
    assert t.language == "pt-BR"


def test_tenant_record_rejects_invalid_status():
    with pytest.raises(ValueError):
        TenantRecord(
            tenant_id="t_abc123",
            wa_id="5511999999999",
            agent_alias="t_abc123",
            workspace_dir="/data/agents/t_abc123/workspace",
            provisioned_at=NOW,
            status="deleted",
        )


def test_tenant_record_rejects_empty_ids():
    with pytest.raises(ValueError):
        TenantRecord(
            tenant_id="",
            wa_id="5511999999999",
            agent_alias="t_abc123",
            workspace_dir="/data/agents/t_abc123/workspace",
            provisioned_at=NOW,
        )


def test_tenant_record_rejects_null_provisioned_at():
    with pytest.raises(ValueError, match="must not be null"):
        TenantRecord(
            tenant_id="t_abc123",
            wa_id="5511999999999",
            agent_alias="t_abc123",
            workspace_dir="/data/agents/t_abc123/workspace",
            provisioned_at=None,
        )


# ── CreditTopUp ──────────────────────────────────────────────────────────

def test_onchain_topup_requires_real_signature():
    with pytest.raises(ValueError, match="never fabricate"):
        CreditTopUp(
            topup_id="top_1",
            tenant_id="t_abc123",
            reference_key="RefKey123",
            usdc_amount=Decimal("10"),
            credited_usd_balance_delta=Decimal("10"),
            confirmed_at=NOW,
            source="onchain",
            tx_signature=None,
        )


def test_onchain_topup_valid_construction():
    t = CreditTopUp(
        topup_id="top_1",
        tenant_id="t_abc123",
        reference_key="RefKey123",
        usdc_amount=Decimal("10"),
        credited_usd_balance_delta=Decimal("10"),
        confirmed_at=NOW,
        source="onchain",
        tx_signature="5x7RealSolanaSignature",
    )
    assert t.tx_signature == "5x7RealSolanaSignature"


def test_trial_grant_must_not_carry_a_signature():
    with pytest.raises(ValueError, match="don't fake one"):
        CreditTopUp(
            topup_id="top_2",
            tenant_id="t_abc123",
            reference_key="trial",
            usdc_amount=Decimal("0"),
            credited_usd_balance_delta=Decimal("1.00"),
            confirmed_at=NOW,
            source="trial_grant",
            tx_signature="not-a-real-tx",
        )


def test_trial_grant_must_have_zero_usdc_amount():
    with pytest.raises(ValueError, match="usdc_amount must be exactly 0"):
        CreditTopUp(
            topup_id="top_2",
            tenant_id="t_abc123",
            reference_key="trial",
            usdc_amount=Decimal("5"),
            credited_usd_balance_delta=Decimal("1.00"),
            confirmed_at=NOW,
            source="trial_grant",
        )


def test_trial_grant_valid_construction():
    t = CreditTopUp(
        topup_id="top_2",
        tenant_id="t_abc123",
        reference_key="trial",
        usdc_amount=Decimal("0"),
        credited_usd_balance_delta=Decimal("1.00"),
        confirmed_at=NOW,
        source="trial_grant",
    )
    assert t.tx_signature is None


def test_topup_rejects_non_positive_credit_delta():
    with pytest.raises(ValueError):
        CreditTopUp(
            topup_id="top_3",
            tenant_id="t_abc123",
            reference_key="trial",
            usdc_amount=Decimal("0"),
            credited_usd_balance_delta=Decimal("0"),
            confirmed_at=NOW,
            source="trial_grant",
        )


# ── CreditDebit ──────────────────────────────────────────────────────────

def test_debit_requires_cost_record_ref():
    with pytest.raises(ValueError, match="cost_record_ref"):
        CreditDebit(
            debit_id="d1",
            tenant_id="t_abc123",
            cost_record_ref="",
            usd_amount=Decimal("0.05"),
            debited_at=NOW,
        )


def test_debit_valid_construction():
    d = CreditDebit(
        debit_id="d1",
        tenant_id="t_abc123",
        cost_record_ref="2026-08-01T12:00:00Z:anthropic:t_abc123",
        usd_amount=Decimal("0.05"),
        debited_at=NOW,
    )
    assert d.usd_amount == Decimal("0.05")


def test_debit_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        CreditDebit(
            debit_id="d1",
            tenant_id="t_abc123",
            cost_record_ref="ref",
            usd_amount=Decimal("0"),
            debited_at=NOW,
        )


# ── compute_balance ──────────────────────────────────────────────────────

def test_compute_balance_trial_then_debits():
    topups = [
        CreditTopUp(
            topup_id="top_1",
            tenant_id="t1",
            reference_key="trial",
            usdc_amount=Decimal("0"),
            credited_usd_balance_delta=Decimal("1.00"),
            confirmed_at=NOW,
            source="trial_grant",
        )
    ]
    debits = [
        CreditDebit(
            debit_id="d1",
            tenant_id="t1",
            cost_record_ref="ref1",
            usd_amount=Decimal("0.30"),
            debited_at=NOW,
        ),
        CreditDebit(
            debit_id="d2",
            tenant_id="t1",
            cost_record_ref="ref2",
            usd_amount=Decimal("0.25"),
            debited_at=NOW,
        ),
    ]
    assert compute_balance(topups, debits) == Decimal("0.45")


def test_compute_balance_can_go_negative():
    """A single expensive turn can push balance below zero before the next
    pre-turn gate check catches it -- the gate's own tolerance policy
    (not this module) decides how negative is acceptable.
    """
    topups = [
        CreditTopUp(
            topup_id="top_1",
            tenant_id="t1",
            reference_key="trial",
            usdc_amount=Decimal("0"),
            credited_usd_balance_delta=Decimal("0.10"),
            confirmed_at=NOW,
            source="trial_grant",
        )
    ]
    debits = [
        CreditDebit(
            debit_id="d1",
            tenant_id="t1",
            cost_record_ref="ref1",
            usd_amount=Decimal("0.50"),
            debited_at=NOW,
        ),
    ]
    assert compute_balance(topups, debits) == Decimal("-0.40")


def test_compute_balance_empty_history_is_zero():
    assert compute_balance([], []) == Decimal("0.00")
