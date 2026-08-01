"""docs/language.md Section 8, items 2-3: separator-swap and date tests."""
from datetime import date
from decimal import Decimal

from rendering.formatting import (
    format_brl,
    format_brl_signed,
    format_competencia,
    format_date,
    format_month_name,
    format_percentage,
    format_usdc,
    format_vencimento,
)


def test_multi_thousand_real_figure_separators():
    value = Decimal("4336.00")
    assert format_brl(value, "pt-BR") == "R$ 4.336,00"
    assert format_brl(value, "en") == "R$4,336.00"


def test_sub_real_centavos_only_figure_separators():
    value = Decimal("0.56")
    assert format_brl(value, "pt-BR") == "R$ 0,56"
    assert format_brl(value, "en") == "R$0.56"


def test_large_figure_thousands_grouping():
    value = Decimal("1234567.89")
    assert format_brl(value, "pt-BR") == "R$ 1.234.567,89"
    assert format_brl(value, "en") == "R$1,234,567.89"


def test_negative_value_gets_explicit_loss_label_not_bare_minus():
    value = Decimal("-150.00")
    pt = format_brl_signed(value, "pt-BR")
    en = format_brl_signed(value, "en")
    assert "prejuízo" in pt
    assert "loss" in en
    assert "R$ 150,00" in pt
    assert "R$150.00" in en


def test_positive_value_has_no_loss_label():
    value = Decimal("150.00")
    assert "prejuízo" not in format_brl_signed(value, "pt-BR")
    assert "loss" not in format_brl_signed(value, "en")


def test_usdc_whole_amount_has_no_decimals():
    assert format_usdc(Decimal("800"), "pt-BR") == "800 USDC"
    assert format_usdc(Decimal("800"), "en") == "800 USDC"


def test_usdc_fractional_amount_keeps_decimals_with_locale_separator():
    assert format_usdc(Decimal("1234.50"), "pt-BR") == "1.234,50 USDC"
    assert format_usdc(Decimal("1234.50"), "en") == "1,234.50 USDC"


def test_date_renders_dd_mm_yyyy_in_portuguese():
    d = date(2026, 7, 5)
    assert format_date(d, "pt-BR") == "05/07/2026"


def test_date_renders_unambiguous_named_month_in_english():
    d = date(2026, 7, 5)
    assert format_date(d, "en") == "Jul 5, 2026"
    # never bare numerals that could be misread as DD/MM
    assert "/" not in format_date(d, "en")


def test_vencimento_never_renders_bare_numerals_in_english():
    """Deliberate deviation from docs/language.md's own illustrative
    English template ('07/31/2026') in favor of its own Section 5.3 rule.
    See formatting.py::format_vencimento and DEVIATIONS.md.
    """
    d = date(2026, 7, 31)
    en = format_vencimento(d, "en")
    assert "/" not in en
    assert en == "Jul 31, 2026"
    assert format_vencimento(d, "pt-BR") == "31/07/2026"


def test_competencia_is_language_invariant():
    assert format_competencia(6, 2026) == "06/2026"


def test_month_name_localized():
    assert format_month_name(6, "pt-BR") == "junho"
    assert format_month_name(6, "en") == "June"
    assert format_month_name(7, "pt-BR") == "julho"
    assert format_month_name(7, "en") == "July"


def test_percentage_formatting():
    assert format_percentage(Decimal("0.15"), "pt-BR") == "15%"
    assert format_percentage(Decimal("0.075"), "en") == "7.5%"
    assert format_percentage(Decimal("0.075"), "pt-BR") == "7,5%"


def test_invalid_language_rejected():
    import pytest

    with pytest.raises(ValueError):
        format_brl(Decimal("1"), "fr")
