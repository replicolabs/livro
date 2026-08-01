"""Locale-aware number, currency, and date formatting.

docs/language.md Section 5: "This is the single highest-risk formatting bug
in the whole feature... treat any code path that renders a number as
needing an explicit, tested locale-aware formatter -- never
string-concatenate a raw float into a message." Every function here takes
a Decimal or date and a language code; none ever guesses the language from
context.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from rendering import validate_language

PT_MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
EN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
EN_MONTHS_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def format_number(value: Decimal, language: str, decimals: int = 2) -> str:
    """Format a Decimal with the correct decimal/thousands separators.

    en convention (period decimal, comma thousands) is what Python's own
    ',' format spec produces natively; pt-BR swaps the two separators from
    that base rendering, per docs/language.md Section 5.1.
    """
    validate_language(language)
    quantum = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
    quantized = value.quantize(quantum, rounding=ROUND_HALF_UP)

    if decimals:
        en_style = f"{quantized:,.{decimals}f}"
    else:
        en_style = f"{quantized:,.0f}"

    if language == "en":
        return en_style

    # pt-BR: swap ',' (thousands) and '.' (decimal) via a single translate
    # table so the two substitutions can never collide mid-swap.
    return en_style.translate(str.maketrans(",.", ".,"))


def format_brl(value: Decimal, language: str) -> str:
    """Render a BRL amount: 'R$ 1.234,56' (pt-BR) vs 'R$1,234.56' (en).

    Space-after-symbol convention follows docs/language.md Section 6's own
    illustrative templates exactly (pt-BR has a space, en does not).
    """
    validate_language(language)
    number = format_number(value, language, decimals=2)
    return f"R$ {number}" if language == "pt-BR" else f"R${number}"


def format_brl_signed(value: Decimal, language: str) -> str:
    """Render a possibly-negative BRL amount with an explicit loss label
    rather than a bare minus sign, per docs/language.md Section 5.1: losses
    must never be visually mistaken for a small positive figure.
    """
    validate_language(language)
    magnitude = format_brl(abs(value), language)
    if value >= 0:
        return magnitude
    label = "prejuízo" if language == "pt-BR" else "loss"
    return f"-{magnitude} ({label})"


def format_usdc(value: Decimal, language: str) -> str:
    """Render a USDC amount, e.g. '800 USDC' / '1.234,50 USDC' (pt-BR) or
    '1,234.5 USDC' (en). Never a bare '$' prefix (docs/language.md 5.2).
    """
    validate_language(language)
    is_whole = value == value.to_integral_value()
    number = format_number(value, language, decimals=0 if is_whole else 2)
    return f"{number} USDC"


def format_date(d: date, language: str) -> str:
    """pt-BR: DD/MM/YYYY. en: unambiguous named-month form ('Jul 5, 2026'),
    never bare MM/DD/YYYY numerals (docs/language.md Section 5.3 -- numeral-
    only English dates are exactly the misread risk this rule exists for).
    """
    validate_language(language)
    if language == "pt-BR":
        return d.strftime("%d/%m/%Y")
    return f"{EN_MONTHS_ABBR[d.month - 1]} {d.day}, {d.year}"


def format_vencimento(d: date, language: str) -> str:
    """Resolves an internal tension in docs/language.md: Section 6's
    illustrative English template literally writes the vencimento as
    '07/31/2026' (bare MM/DD/YYYY numerals), but Section 5.3 explicitly
    bans exactly that shape ("Do not use 07/05/2026 in English mode
    without a name for the month"). Section 6 itself says templates are
    illustrative and formatting RULES must be preserved exactly, so this
    follows Section 5.3's unambiguous date rendering rather than the
    illustrative example's literal numerals. See DEVIATIONS.md.
    """
    return format_date(d, language)


def format_competencia(month: int, year: int) -> str:
    """'MM/YYYY', identical in both languages -- this is a specific DARF
    field format (like darf_code), not a general date, so the DD/MM vs
    MM/DD ambiguity Section 5.3 warns about doesn't apply the same way.
    """
    return f"{month:02d}/{year}"


def format_month_name(month: int, language: str) -> str:
    """A prose month name (e.g. 'junho' / 'June'), distinct from the
    numeral competencia field above.
    """
    validate_language(language)
    return (PT_MONTHS if language == "pt-BR" else EN_MONTHS)[month - 1]


def format_percentage(rate: Decimal, language: str) -> str:
    """Render a rate already expressed as a fraction (0.15) as '15%',
    (0.075) as '7.5%'/'7,5%' -- the minimal decimal places that round-trip
    the value exactly, never padded with a trailing insignificant zero.
    """
    validate_language(language)
    percent_value = rate * 100
    for decimals in (0, 1, 2):
        quantum = Decimal(1).scaleb(-decimals) if decimals else Decimal(1)
        if percent_value.quantize(quantum, rounding=ROUND_HALF_UP) == percent_value:
            break
    return f"{format_number(percent_value, language, decimals=decimals)}%"
