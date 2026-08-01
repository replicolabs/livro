"""BACEN PTAX weekend/holiday fallback resolution. CLAUDE.md Section 6.1.

This module contains only the date-walking fallback rule. The actual HTTP
call to the Olinda PTAX endpoint is network I/O and belongs to the skill/SOP
glue (http_request tool), not this pure module -- tests supply a
`quote_lookup` stand-in instead of a live connection (CLAUDE.md Section 8.2:
mocked RPC/API, no live network in tests).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Callable, Optional

QuoteLookup = Callable[[date], Optional[Decimal]]

MAX_LOOKBACK_DAYS = 10


@dataclass(frozen=True)
class PtaxResolution:
    requested_date: date
    date_used: date
    rate: Decimal
    quote_type: str
    fallback_rule_applied: bool


class NoPtaxQuoteFoundError(RuntimeError):
    pass


def resolve_ptax_rate(
    receipt_date: date,
    quote_lookup: QuoteLookup,
    quote_type: str = "venda",
    max_lookback_days: int = MAX_LOOKBACK_DAYS,
) -> PtaxResolution:
    """Resolve the PTAX rate for receipt_date, walking backward on no publication.

    quote_lookup(d) returns the published rate for date d, or None if PTAX has
    no quote for that date (weekend, holiday). Walks backward day-by-day, up to
    max_lookback_days, and records whether the fallback rule fired.
    """
    for offset in range(max_lookback_days + 1):
        candidate = receipt_date - timedelta(days=offset)
        rate = quote_lookup(candidate)
        if rate is not None:
            return PtaxResolution(
                requested_date=receipt_date,
                date_used=candidate,
                rate=rate,
                quote_type=quote_type,
                fallback_rule_applied=(offset > 0),
            )

    raise NoPtaxQuoteFoundError(
        f"no PTAX quote found within {max_lookback_days} days before {receipt_date}"
    )
