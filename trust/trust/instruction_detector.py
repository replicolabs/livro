"""Deterministic fund-moving-instruction phrase detector, bilingual.

Same design discipline as rendering/rendering/language_switch.py: a curated
set of direct, redirect/refund-shaped trigger phrases, normalized for
accents and case, never a generic "does this sound suspicious" heuristic.
This is intentionally biased toward over-flagging rather than under-flagging
-- a false positive here just means an ordinary message gets surfaced as an
FYI or a confirmation prompt (cheap); a false negative means a real
injection attempt slips through unflagged (the failure this module exists
to prevent). See CLAUDE.md Section 1.4 and trust/__init__.py.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TRIGGER_PHRASES = (
    # English
    "send it to",
    "send the payment to",
    "send the funds to",
    "please refund to",
    "refund to",
    "refund it to",
    "redirect the payment",
    "redirect this payment",
    "change the destination",
    "change the address",
    "change the wallet",
    "use this address instead",
    "send to this address instead",
    "cancel the invoice and send",
    "update the wallet address",
    "new wallet address",
    "transfer it to",
    "wire it to",
    "instead of the invoice address",
    # Portuguese (pre-normalization forms; accents stripped at match time)
    "envie para",
    "envia para",
    "manda para",
    "mande para",
    "por favor reembolse",
    "reembolsar para",
    "reembolse para",
    "redirecionar o pagamento",
    "redireciona o pagamento",
    "mude o endereco",
    "muda o endereco",
    "mude a carteira",
    "use este endereco",
    "usa este endereco",
    "em vez do endereco",
    "ao inves do endereco",
    "cancele a fatura e envie",
    "atualize a carteira",
    "novo endereco da carteira",
    "novo endereco de carteira",
    "transfira para",
    "transferir para",
)

# A bare base58-shaped token long enough to plausibly be a Solana address.
# Supporting signal only -- never sufficient alone (a client's own paying
# address legitimately appears in ordinary transaction data), but combined
# with a trigger phrase it raises confidence for the audit log.
_SOLANA_ADDRESS_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


@dataclass(frozen=True)
class DetectionResult:
    detected: bool
    matched_phrase: str | None
    contains_address_like_token: bool


def detect_fund_moving_instruction(text: str) -> DetectionResult:
    normalized = _normalize(text)

    matched = next((phrase for phrase in TRIGGER_PHRASES if phrase in normalized), None)
    has_address = bool(_SOLANA_ADDRESS_RE.search(text))

    return DetectionResult(
        detected=matched is not None,
        matched_phrase=matched,
        contains_address_like_token=has_address,
    )
