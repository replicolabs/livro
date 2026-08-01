"""Credit top-up flow: reuses the exact Solana Pay pattern already built for
client invoicing (shared/skills/livro/draft_invoice/SKILL.md), with two
substitutions -- a fixed recipient (the owner's own wallet, not a fresh
per-invoice address) and a per-tenant `reference` key for correlation.

Network I/O (the actual Solana RPC calls) is kept behind an injected seam,
same discipline as tax_engine/ptax.py's `quote_lookup` callable -- this
module's matching/correlation logic is pure and independently testable
without a live RPC connection.

A "pending top-up" (a reference key issued but not yet matched to an
on-chain payment) is deliberately NOT a platform_ledger.CreditTopUp -- that
type is reserved for CONFIRMED, immutable financial facts. Pending intents
are simple dicts in their own JSONL file until a real payment arrives, then
promoted into a validated CreditTopUp (see promote_pending_topup).
"""
from __future__ import annotations

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Awaitable, Callable, Optional

import base58

from platform_ledger.records import CreditTopUp

from gate.balance import append_topup

# Shaped-down transaction info -- CLAUDE.md Section 6.2's own principle
# ("shape RPC responses down before they hit reasoning") applied here too:
# only signature/account_keys/amount/timestamp ever leave the RPC-calling
# layer, never a raw getTransaction blob.
GetSignaturesFn = Callable[[str], Awaitable[list[str]]]
GetTransactionFn = Callable[[str], Awaitable["ShapedTransaction"]]


@dataclass(frozen=True)
class ShapedTransaction:
    signature: str
    account_keys: tuple[str, ...]
    usdc_amount: Decimal
    block_time: datetime


@dataclass(frozen=True)
class PendingTopUp:
    reference_key: str
    tenant_id: str
    created_at: datetime
    suggested_amount: Optional[Decimal] = None


def generate_reference_key() -> str:
    """A random 32-byte value, base58-encoded -- Solana Pay's `reference`
    is a pubkey-shaped correlation tag, never used to sign anything, so it
    doesn't need to be a valid curve point, only unique and base58-formatted.
    """
    return base58.b58encode(secrets.token_bytes(32)).decode("ascii")


def build_topup_uri(
    owner_wallet: str,
    usdc_mint: str,
    reference_key: str,
    suggested_amount: Optional[Decimal] = None,
) -> str:
    """Same solana: URI shape as draft_invoice's client-payment links."""
    uri = f"solana:{owner_wallet}?spl-token={usdc_mint}&reference={reference_key}"
    if suggested_amount is not None:
        uri = f"solana:{owner_wallet}?amount={suggested_amount}&spl-token={usdc_mint}&reference={reference_key}"
    return uri


def _pending_path(platform_dir: Path) -> Path:
    return platform_dir / "pending_topups.jsonl"


def create_pending_topup(
    platform_dir: Path,
    tenant_id: str,
    owner_wallet: str,
    usdc_mint: str,
    suggested_amount: Optional[Decimal] = None,
) -> tuple[PendingTopUp, str]:
    """Generate a fresh reference key, record the pending intent (never a
    CreditTopUp yet -- draft_invoice's own rule: 'do not create the
    ledger_entry until a payment actually arrives'), return the Solana Pay URI.
    """
    reference_key = generate_reference_key()
    pending = PendingTopUp(
        reference_key=reference_key,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
        suggested_amount=suggested_amount,
    )
    platform_dir.mkdir(parents=True, exist_ok=True)
    with _pending_path(platform_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "reference_key": pending.reference_key,
            "tenant_id": pending.tenant_id,
            "created_at": pending.created_at.isoformat(),
            "suggested_amount": str(pending.suggested_amount) if pending.suggested_amount else None,
        }) + "\n")

    uri = build_topup_uri(owner_wallet, usdc_mint, reference_key, suggested_amount)
    return pending, uri


def load_open_pending_topups(platform_dir: Path) -> list[PendingTopUp]:
    """All pending topups minus any already matched/promoted (tracked by
    absence from a simple 'matched_references.jsonl' marker file).
    """
    path = _pending_path(platform_dir)
    if not path.exists():
        return []

    matched_path = platform_dir / "matched_references.jsonl"
    matched_refs = set()
    if matched_path.exists():
        with matched_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    matched_refs.add(json.loads(line)["reference_key"])

    result = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r["reference_key"] in matched_refs:
                continue
            result.append(PendingTopUp(
                reference_key=r["reference_key"],
                tenant_id=r["tenant_id"],
                created_at=datetime.fromisoformat(r["created_at"]),
                suggested_amount=Decimal(r["suggested_amount"]) if r.get("suggested_amount") else None,
            ))
    return result


def match_transaction_to_pending(
    tx: ShapedTransaction, open_pending: list[PendingTopUp]
) -> Optional[PendingTopUp]:
    """Pure correlation: does this transaction's account list contain any
    currently-open pending top-up's reference key?
    """
    for pending in open_pending:
        if pending.reference_key in tx.account_keys:
            return pending
    return None


def promote_pending_topup(
    platform_dir: Path, pending: PendingTopUp, tx: ShapedTransaction
) -> CreditTopUp:
    """A match was found: record it as matched (so it's never re-processed)
    and append the confirmed, validated CreditTopUp.
    """
    matched_path = platform_dir / "matched_references.jsonl"
    with matched_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"reference_key": pending.reference_key, "tx_signature": tx.signature}) + "\n")

    topup = CreditTopUp(
        topup_id=f"top_{uuid.uuid4().hex[:12]}",
        tenant_id=pending.tenant_id,
        reference_key=pending.reference_key,
        usdc_amount=tx.usdc_amount,
        credited_usd_balance_delta=tx.usdc_amount,  # 1:1 USDC-to-USD-credit, no markup
        confirmed_at=tx.block_time,
        source="onchain",
        tx_signature=tx.signature,
    )
    append_topup(platform_dir, topup)
    return topup


async def poll_for_topups(
    platform_dir: Path,
    owner_wallet: str,
    get_signatures: GetSignaturesFn,
    get_transaction: GetTransactionFn,
) -> list[CreditTopUp]:
    """One poll cycle: fetch recent signatures for the owner's wallet,
    fetch shaped transaction details for each, match against every
    currently-open tenant's pending top-up, promote any matches. One RPC
    poll of one address serves every tenant -- not a per-tenant SOP, since
    N tenants independently polling the same address would be redundant
    and racy (see the approved plan's Section 5 reasoning).
    """
    open_pending = load_open_pending_topups(platform_dir)
    if not open_pending:
        return []

    promoted: list[CreditTopUp] = []
    signatures = await get_signatures(owner_wallet)
    for sig in signatures:
        tx = await get_transaction(sig)
        match = match_transaction_to_pending(tx, open_pending)
        if match is not None:
            promoted.append(promote_pending_topup(platform_dir, match, tx))
            open_pending = [p for p in open_pending if p.reference_key != match.reference_key]

    return promoted
