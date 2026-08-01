"""Do-not-translate official term list. docs/language.md Section 4.

Every term below must appear verbatim in a rendered message in EITHER
language, whenever the message's content would naturally include it. This
module doesn't translate anything itself -- templates.py is responsible for
using these literal strings rather than a translated substitute -- but it
gives tests a single source of truth to check rendered output against.
"""
from __future__ import annotations

DO_NOT_TRANSLATE_TERMS = (
    "Carnê-Leão",
    "DARF",
    "PTAX",
    "BACEN",
    "Contador",
    "Bens e Direitos",
    "IN 1888",
    "DeCripto",
    "Competência",
    "Vencimento",
    "DIRPF",
    "GCAP",
    "Nota Fiscal",
    "NFS-e",
    "MEI",
)


def missing_terms(text: str, terms: tuple[str, ...] = DO_NOT_TRANSLATE_TERMS) -> list[str]:
    """Return which of `terms` are absent from `text`.

    Case-insensitive: the illustrative templates in docs/language.md
    Section 6 render "competência"/"vencimento" lowercase mid-sentence
    while Section 4's table lists them capitalized -- what matters is the
    term itself is present untranslated, not its capitalization.
    """
    lowered = text.lower()
    return [term for term in terms if term.lower() not in lowered]
