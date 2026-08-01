"""Loading of dated, sourced tax-table config objects.

Tax brackets, thresholds, and rates are never inline literals in calculation
code (CLAUDE.md Section 5). They live in tax_tables/*.json, each carrying
effective_from / source_url / verified_on / verified fields so callers can
tell a confirmed primary-source figure from an unverified placeholder.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

TABLES_DIR = Path(__file__).resolve().parent.parent / "tax_tables"


@dataclass(frozen=True)
class TableMeta:
    effective_from: str
    source_url: str
    verified_on: str
    verified: bool
    caveat: str = ""


def _load_json(name: str) -> dict:
    path = TABLES_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_table(name: str) -> dict:
    """Load a dated tax-table JSON file by filename (e.g. 'carne_leao_2026.json')."""
    return _load_json(name)


def meta_from(table: dict) -> TableMeta:
    return TableMeta(
        effective_from=table["effective_from"],
        source_url=table["source_url"],
        verified_on=table["verified_on"],
        verified=bool(table.get("verified", False)),
        caveat=table.get("verification_caveat", ""),
    )
