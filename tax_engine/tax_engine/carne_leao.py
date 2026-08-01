"""Carne-Leao: monthly progressive tax on ordinary income at receipt.

CLAUDE.md Section 5.1. All money math uses Decimal; the caller passes in a
loaded table dict (see tables.load_table) rather than this module reaching
into the filesystem itself, keeping the arithmetic pure and mockable.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CarneLeaoDeductions:
    inss_monthly: Decimal = Decimal("0")
    dependents_count: int = 0
    alimony_monthly: Decimal = Decimal("0")
    livro_caixa_expenses_monthly: Decimal = Decimal("0")


@dataclass(frozen=True)
class CarneLeaoResult:
    gross_income: Decimal
    deductions_applied: Decimal
    deduction_path: str
    taxable_base: Decimal
    bracket_rate: Decimal
    bracket_deduction: Decimal
    tax_before_sliding_reduction: Decimal
    sliding_reduction_applied: Decimal
    tax_due: Decimal
    darf_code: str
    competencia: str
    vencimento: str
    table_effective_from: str
    table_source_url: str
    table_verified: bool
    table_caveat: str
    sliding_reduction_verified: bool
    sliding_reduction_caveat: str


def _bracket_for(base: Decimal, brackets: list[dict]) -> dict:
    """Return the bracket whose up_to bound is the first >= base (None up_to = top bracket)."""
    for bracket in brackets:
        up_to = bracket["up_to"]
        if up_to is None or base <= Decimal(str(up_to)):
            return bracket
    return brackets[-1]


def _sliding_reduction(gross_income: Decimal, tax_before: Decimal, table: dict) -> Decimal:
    """Lei 15.270/2025 Art. 3-A reduction. Returns the reduction amount (>= 0).

    Reconstructed and verified against all 5 of Receita Federal's own
    worked examples (gov.br "Exemplos de aplicacao da Lei 15.270/2025",
    fetched and reproduced exactly on 2026-07-30 -- see
    tests/test_carne_leao.py::test_receita_worked_example_* for each one).
    The earlier version of this module (see git history / DEVIATIONS.md
    Section 5d/9) implemented a two-piece rule with a hard "base <= 5000 =>
    zero" special case and fed it the post-deduction taxable base; that was
    wrong on two counts, both corrected here:

    1. The formula's input is GROSS monthly income (Receita's own text:
       "se utiliza... o valor do salario, e nao o da base de calculo"),
       not the taxable base after deductions.
    2. There is no separate "<=5000 => zero" rule at all -- it is ONE
       continuous formula, `reduction = max(0, intercept - slope * gross)`,
       capped at `tax_before` (never a rebate larger than the tax itself)
       and zeroed above `upper_bound`. The apparent R$5,000 cliff in the
       earlier version was an artifact of computing tax_before on the wrong
       base; the real mechanism has no discontinuity.
    """
    band = table.get("sliding_reduction")
    if not band:
        return Decimal("0")

    upper = Decimal(str(band["upper_bound"]))
    if gross_income > upper:
        return Decimal("0")

    intercept = Decimal(str(band["formula_intercept"]))
    slope = Decimal(str(band["formula_slope"]))
    reduction = max(Decimal("0"), intercept - slope * gross_income)
    return min(_q(reduction), tax_before)


def compute_carne_leao(
    gross_income: Decimal,
    deductions: CarneLeaoDeductions,
    table: dict,
    competencia: str,
    vencimento: str,
) -> CarneLeaoResult:
    """Compute one month's Carne-Leao liability.

    gross_income: sum of this month's income-leg ledger entries' brl_value.
    competencia/vencimento: caller-supplied (MM/YYYY and due-date string) since
    calendar logic (last business day of next month, holiday calendar) belongs
    to the caller, not this pure arithmetic module.

    Deduction path: per Receita's own worked examples, the "desconto
    simplificado" (a flat monthly amount, `table["simplified_discount_cap_monthly"]`)
    REPLACES every itemized deduction -- it is never combined with them. The
    taxpayer takes whichever is larger (Receita: "a fonte pagadora deve
    considerar as deducoes legais permitidas" whenever they exceed the flat
    amount). Since a larger deduction can never increase tax on a monotonic
    progressive table, taking max(itemized_total, simplified_discount) is
    equivalent to computing both and picking the lower tax, without needing
    to actually run the bracket lookup twice.
    """
    dependent_deduction = Decimal(str(table["dependent_deduction"])) * deductions.dependents_count
    itemized_total = _q(
        deductions.inss_monthly
        + dependent_deduction
        + deductions.alimony_monthly
        + deductions.livro_caixa_expenses_monthly
    )
    simplified_discount = Decimal(str(table["simplified_discount_cap_monthly"]))

    if simplified_discount > itemized_total:
        deductions_applied = simplified_discount
        deduction_path = "simplified"
    else:
        deductions_applied = itemized_total
        deduction_path = "itemized"

    taxable_base = max(Decimal("0"), _q(gross_income - deductions_applied))

    bracket = _bracket_for(taxable_base, table["brackets"])
    rate = Decimal(str(bracket["rate"]))
    bracket_deduction = Decimal(str(bracket["deduction"]))

    tax_before = max(Decimal("0"), _q(taxable_base * rate - bracket_deduction))

    reduction = _sliding_reduction(gross_income, tax_before, table)
    tax_due = max(Decimal("0"), _q(tax_before - reduction))

    band = table.get("sliding_reduction") or {}
    sliding_reduction_verified = bool(band.get("verified", False))
    sliding_reduction_caveat = band.get("mechanism_note", "")

    overall_verified = bool(table.get("verified", False)) and (
        reduction == 0 or sliding_reduction_verified
    )

    return CarneLeaoResult(
        gross_income=_q(gross_income),
        deductions_applied=deductions_applied,
        deduction_path=deduction_path,
        taxable_base=taxable_base,
        bracket_rate=rate,
        bracket_deduction=bracket_deduction,
        tax_before_sliding_reduction=tax_before,
        sliding_reduction_applied=reduction,
        tax_due=tax_due,
        darf_code="0190",
        competencia=competencia,
        vencimento=vencimento,
        table_effective_from=table["effective_from"],
        table_source_url=table["source_url"],
        table_verified=overall_verified,
        table_caveat=table.get("verification_caveat", ""),
        sliding_reduction_verified=sliding_reduction_verified,
        sliding_reduction_caveat=sliding_reduction_caveat,
    )
