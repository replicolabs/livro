from datetime import datetime, timezone
from decimal import Decimal

import pytest

from gate.balance import get_balance
from gate.topup_watcher import (
    ShapedTransaction,
    build_topup_uri,
    create_pending_topup,
    generate_reference_key,
    load_open_pending_topups,
    match_transaction_to_pending,
    poll_for_topups,
    promote_pending_topup,
)

OWNER_WALLET = "OwnerWa11etAddre55111111111111111111111111"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def test_generate_reference_key_is_unique_and_base58():
    keys = {generate_reference_key() for _ in range(50)}
    assert len(keys) == 50
    for k in keys:
        assert all(c not in "0OIl" for c in k)  # base58 alphabet excludes these


def test_build_topup_uri_with_amount():
    uri = build_topup_uri(OWNER_WALLET, USDC_MINT, "RefKey123", Decimal("10"))
    assert uri.startswith(f"solana:{OWNER_WALLET}?amount=10&spl-token={USDC_MINT}&reference=RefKey123")


def test_build_topup_uri_without_amount():
    uri = build_topup_uri(OWNER_WALLET, USDC_MINT, "RefKey123")
    assert "amount=" not in uri
    assert "reference=RefKey123" in uri


def test_create_pending_topup_and_load_open(tmp_path):
    pending, uri = create_pending_topup(tmp_path, "t_1", OWNER_WALLET, USDC_MINT, Decimal("5"))

    assert pending.tenant_id == "t_1"
    assert "reference=" + pending.reference_key in uri

    open_pending = load_open_pending_topups(tmp_path)
    assert len(open_pending) == 1
    assert open_pending[0].reference_key == pending.reference_key


def test_match_transaction_to_pending_finds_correct_reference():
    from gate.topup_watcher import PendingTopUp

    open_pending = [
        PendingTopUp(reference_key="RefA", tenant_id="t_a", created_at=datetime.now(timezone.utc)),
        PendingTopUp(reference_key="RefB", tenant_id="t_b", created_at=datetime.now(timezone.utc)),
    ]
    tx = ShapedTransaction(
        signature="sig1",
        account_keys=(OWNER_WALLET, "RefB", "SomeOtherAccount"),
        usdc_amount=Decimal("5"),
        block_time=datetime.now(timezone.utc),
    )
    match = match_transaction_to_pending(tx, open_pending)
    assert match is not None
    assert match.tenant_id == "t_b"


def test_match_transaction_to_pending_no_match_returns_none():
    from gate.topup_watcher import PendingTopUp

    open_pending = [PendingTopUp(reference_key="RefA", tenant_id="t_a", created_at=datetime.now(timezone.utc))]
    tx = ShapedTransaction(
        signature="sig1", account_keys=(OWNER_WALLET, "Unrelated"),
        usdc_amount=Decimal("5"), block_time=datetime.now(timezone.utc),
    )
    assert match_transaction_to_pending(tx, open_pending) is None


def test_promote_pending_topup_credits_balance_and_marks_matched(tmp_path):
    pending, _ = create_pending_topup(tmp_path, "t_1", OWNER_WALLET, USDC_MINT, Decimal("10"))
    tx = ShapedTransaction(
        signature="sig1", account_keys=(OWNER_WALLET, pending.reference_key),
        usdc_amount=Decimal("10"), block_time=datetime.now(timezone.utc),
    )

    topup = promote_pending_topup(tmp_path, pending, tx)

    assert topup.source == "onchain"
    assert topup.tx_signature == "sig1"
    assert topup.credited_usd_balance_delta == Decimal("10")
    assert get_balance(tmp_path, "t_1") == Decimal("10.00")

    # matched -- no longer "open"
    assert load_open_pending_topups(tmp_path) == []


@pytest.mark.asyncio
async def test_poll_for_topups_matches_and_promotes_across_tenants(tmp_path):
    pending_1, _ = create_pending_topup(tmp_path, "t_1", OWNER_WALLET, USDC_MINT, Decimal("10"))
    pending_2, _ = create_pending_topup(tmp_path, "t_2", OWNER_WALLET, USDC_MINT, Decimal("5"))

    tx_for_t1 = ShapedTransaction(
        signature="sig_t1", account_keys=(OWNER_WALLET, pending_1.reference_key),
        usdc_amount=Decimal("10"), block_time=datetime.now(timezone.utc),
    )
    tx_unrelated = ShapedTransaction(
        signature="sig_unrelated", account_keys=(OWNER_WALLET, "SomeoneElse"),
        usdc_amount=Decimal("1"), block_time=datetime.now(timezone.utc),
    )

    async def get_signatures(wallet: str) -> list[str]:
        assert wallet == OWNER_WALLET
        return ["sig_t1", "sig_unrelated"]

    async def get_transaction(sig: str) -> ShapedTransaction:
        return {"sig_t1": tx_for_t1, "sig_unrelated": tx_unrelated}[sig]

    promoted = await poll_for_topups(tmp_path, OWNER_WALLET, get_signatures, get_transaction)

    assert len(promoted) == 1
    assert promoted[0].tenant_id == "t_1"
    assert get_balance(tmp_path, "t_1") == Decimal("10.00")
    assert get_balance(tmp_path, "t_2") == Decimal("0.00")  # t_2's top-up still pending
    assert len(load_open_pending_topups(tmp_path)) == 1  # only t_2's remains open


@pytest.mark.asyncio
async def test_poll_for_topups_returns_empty_when_no_pending_at_all(tmp_path):
    async def get_signatures(wallet: str):
        raise AssertionError("should never call RPC when there's nothing pending to match")

    async def get_transaction(sig: str):
        raise AssertionError("unreachable")

    promoted = await poll_for_topups(tmp_path, OWNER_WALLET, get_signatures, get_transaction)
    assert promoted == []
