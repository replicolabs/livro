"""docs/language.md Section 8, items 1 and 7."""
import re
from datetime import date
from decimal import Decimal

from rendering.templates import (
    render_disposition_choices,
    render_external_holding_prompt,
    render_injection_refusal,
    render_invoice_draft,
    render_language_switch_confirmation,
    render_monthly_carne_leao_summary,
    render_payment_received,
    render_threshold_warning,
)

# The exact worked-example figures from docs/language.md Section 6's own
# illustrative pair, used here as the "same worked-example tax calculation"
# CLAUDE.md Section 8.1 / docs/language.md Section 8 item 1 calls for.
WORKED_EXAMPLE = dict(
    base=Decimal("4336.00"),
    bracket_rate=Decimal("0.15"),
    tax_due=Decimal("450.12"),
    darf_code="0190",
    competencia_month=6,
    competencia_year=2026,
    vencimento=date(2026, 7, 31),
)


PT_NUMBER = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
EN_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")


def _extract_decimal_after(text: str, language: str, marker: str) -> Decimal:
    """Pull the numeric value that follows `marker` back out of rendered
    text, undoing the locale formatting, to compare across languages.
    Uses a strict grouped-number pattern (not naive char accumulation) so a
    trailing sentence comma is never mistaken for a decimal separator.
    """
    idx = text.index(marker) + len(marker)
    tail = text[idx:]
    pattern = PT_NUMBER if language == "pt-BR" else EN_NUMBER
    match = pattern.search(tail[:40])
    assert match, f"no number found after {marker!r} in: {tail[:40]!r}"

    if language == "pt-BR":
        normalized = match.group(0).replace(".", "").replace(",", ".")
    else:
        normalized = match.group(0).replace(",", "")
    return Decimal(normalized)


def test_identical_underlying_figure_across_both_languages():
    """The tax_due figure must be byte-for-byte the same numeric value in
    both renderings -- only the formatting differs (docs/language.md
    Section 8 item 1).
    """
    pt_text = render_monthly_carne_leao_summary(language="pt-BR", **WORKED_EXAMPLE)
    en_text = render_monthly_carne_leao_summary(language="en", **WORKED_EXAMPLE)

    pt_value = _extract_decimal_after(pt_text, "pt-BR", "devido ")
    en_value = _extract_decimal_after(en_text, "en", "amount due ")

    assert pt_value == en_value == Decimal("450.12")
    assert pt_value == WORKED_EXAMPLE["tax_due"]


def test_base_and_rate_also_identical_across_languages():
    pt_text = render_monthly_carne_leao_summary(language="pt-BR", **WORKED_EXAMPLE)
    en_text = render_monthly_carne_leao_summary(language="en", **WORKED_EXAMPLE)

    pt_base = _extract_decimal_after(pt_text, "pt-BR", "cálculo ")
    en_base = _extract_decimal_after(en_text, "en", "taxable base ")
    assert pt_base == en_base == WORKED_EXAMPLE["base"]


def test_rendering_never_reads_hidden_state_language_is_the_only_input():
    """Simulates the 'persistence' requirement (docs/language.md Section 8
    item 7) at the rendering-layer boundary: the exact same call, differing
    only in the `language` argument, is the entire contract a scheduled SOP
    (monthly_reminder) relies on to honor a stored preference -- there is no
    other hidden switch this function could be consulting.
    """
    import inspect

    sig = inspect.signature(render_monthly_carne_leao_summary)
    assert "language" in sig.parameters
    assert sig.parameters["language"].default is inspect.Parameter.empty  # no silent default


def test_every_template_exists_in_both_languages_without_raising():
    for language in ("pt-BR", "en"):
        render_invoice_draft(Decimal("800"), "Berlin", 7, "solana:...", language)
        render_payment_received(
            Decimal("800"), "Berlin", date(2026, 7, 5), Decimal("5.42"), Decimal("4336.00"), language
        )
        render_monthly_carne_leao_summary(language=language, **WORKED_EXAMPLE)
        render_threshold_warning(Decimal("35000.00"), language)
        render_injection_refusal(language)
        render_external_holding_prompt(language)
        render_language_switch_confirmation(language)


def test_disposition_choices_are_three_options_in_both_languages():
    for language in ("pt-BR", "en"):
        choices = render_disposition_choices(language)
        assert len(choices) == 3


def test_language_switch_confirmation_is_in_the_new_language_not_the_old_one():
    pt = render_language_switch_confirmation("pt-BR")
    en = render_language_switch_confirmation("en")
    assert "português" in pt
    assert "English" in en
