"""IN 1888 / DeCripto monthly self-report threshold watch. CLAUDE.md Section 5.5."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

APPROACHING_FRACTION = Decimal("0.8")


@dataclass(frozen=True)
class ThresholdStatus:
    cumulative_volume_brl: Decimal
    threshold_brl: Decimal
    fraction_of_threshold: Decimal
    approaching: bool
    exceeded: bool
    table_effective_from: str
    table_source_url: str
    table_verified: bool
    table_caveat: str


def check_threshold(cumulative_volume_brl: Decimal, table: dict) -> ThresholdStatus:
    """cumulative_volume_brl: sum of this calendar month's income + disposal legs.

    `approaching` fires at 80% of the threshold, not before, so threshold_watch
    can proactively flag it ahead of the line rather than only after crossing.
    """
    threshold = Decimal(str(table["monthly_threshold_brl"]))
    fraction = (cumulative_volume_brl / threshold) if threshold > 0 else Decimal("0")

    return ThresholdStatus(
        cumulative_volume_brl=cumulative_volume_brl,
        threshold_brl=threshold,
        fraction_of_threshold=fraction,
        approaching=fraction >= APPROACHING_FRACTION and cumulative_volume_brl < threshold,
        exceeded=cumulative_volume_brl >= threshold,
        table_effective_from=table["effective_from"],
        table_source_url=table["source_url"],
        table_verified=bool(table.get("verified", False)),
        table_caveat=table.get("verification_caveat", ""),
    )
