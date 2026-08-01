"""docs/language.md Section 8, item 4: every do-not-translate term must
appear verbatim in a rendered message that would naturally contain it, in
BOTH languages.
"""
from datetime import date
from decimal import Decimal

from rendering.templates import (
    render_monthly_carne_leao_summary,
    render_threshold_warning,
)
from rendering.terms import missing_terms


def test_carne_leao_summary_preserves_all_relevant_terms():
    for language in ("pt-BR", "en"):
        text = render_monthly_carne_leao_summary(
            base=Decimal("4336.00"),
            bracket_rate=Decimal("0.15"),
            tax_due=Decimal("450.12"),
            darf_code="0190",
            competencia_month=6,
            competencia_year=2026,
            vencimento=date(2026, 7, 31),
            language=language,
        )
        relevant = ("Carnê-Leão", "DARF", "Competência", "Vencimento", "Contador")
        assert missing_terms(text, relevant) == [], f"{language}: {text}"


def test_threshold_warning_preserves_in_1888():
    for language in ("pt-BR", "en"):
        text = render_threshold_warning(Decimal("35000.00"), language)
        assert missing_terms(text, ("IN 1888", "Contador")) == [], f"{language}: {text}"
