"""Hand-worked regression tests for Carne-Leao. CLAUDE.md Section 8.1.

Bracket math is exercised in isolation (BRACKETS_ONLY_TABLE, both deduction
paths zeroed out), then the real 2026 table's simplified-vs-itemized
deduction choice and the Lei 15.270/2025 sliding reduction are each tested
against Receita Federal's own worked examples (gov.br "Exemplos de
aplicacao da Lei 15.270/2025", fetched and reproduced exactly on
2026-07-30) -- these are the permanent worked-example regression tests
CLAUDE.md Section 8.1 asks for, checked against Receita's own tool/examples
rather than a hand-derived guess.
"""
from decimal import Decimal

from tax_engine.carne_leao import CarneLeaoDeductions, compute_carne_leao

COMPETENCIA = "07/2026"
VENCIMENTO = "2026-08-31"


def _run(gross, table, **deduction_kwargs):
    deductions = CarneLeaoDeductions(**{
        "inss_monthly": Decimal("0"),
        "dependents_count": 0,
        "alimony_monthly": Decimal("0"),
        "livro_caixa_expenses_monthly": Decimal("0"),
        **deduction_kwargs,
    })
    return compute_carne_leao(Decimal(str(gross)), deductions, table, COMPETENCIA, VENCIMENTO)


# Pure per-bracket math, isolated from BOTH the simplified-discount and the
# sliding-reduction mechanisms (simplified_discount_cap_monthly=0, no
# sliding_reduction block) -- an artificial fixture, not a real-world table,
# so these specific hand-picked incomes land exactly where each test expects.
BRACKETS_ONLY_TABLE = {
    "effective_from": "2026-01-01",
    "source_url": "https://www.gov.br/receitafederal/pt-br/assuntos/meu-imposto-de-renda/tabelas/2026",
    "verified_on": "2026-07-30",
    "verified": True,
    "dependent_deduction": 189.59,
    "simplified_discount_cap_monthly": 0,
    "brackets": [
        {"up_to": 2428.80, "rate": 0.0, "deduction": 0.0},
        {"up_to": 2826.65, "rate": 0.075, "deduction": 182.16},
        {"up_to": 3751.05, "rate": 0.15, "deduction": 394.16},
        {"up_to": 4664.68, "rate": 0.225, "deduction": 675.49},
        {"up_to": None, "rate": 0.275, "deduction": 908.73},
    ],
}


def test_exemption_bracket():
    r = _run(2000, BRACKETS_ONLY_TABLE)
    assert r.bracket_rate == Decimal("0.0")
    assert r.tax_due == Decimal("0.00")


def test_bracket_7_5_percent():
    r = _run(2600, BRACKETS_ONLY_TABLE)
    # 2600 * 0.075 - 182.16 = 12.84
    assert r.tax_before_sliding_reduction == Decimal("12.84")
    assert r.tax_due == Decimal("12.84")


def test_bracket_15_percent():
    r = _run(3200, BRACKETS_ONLY_TABLE)
    # 3200 * 0.15 - 394.16 = 85.84
    assert r.tax_before_sliding_reduction == Decimal("85.84")
    assert r.tax_due == Decimal("85.84")


def test_bracket_22_5_percent():
    r = _run(4000, BRACKETS_ONLY_TABLE)
    # 4000 * 0.225 - 675.49 = 224.51
    assert r.tax_before_sliding_reduction == Decimal("224.51")
    assert r.tax_due == Decimal("224.51")


def test_bracket_27_5_percent_without_sliding_reduction():
    r = _run(8000, BRACKETS_ONLY_TABLE)
    # 8000 * 0.275 - 908.73 = 1291.27
    assert r.tax_before_sliding_reduction == Decimal("1291.27")
    assert r.tax_due == Decimal("1291.27")


def test_dependents_and_other_deductions_reduce_base_to_exempt(carne_leao_table):
    r = _run(
        3000,
        carne_leao_table,
        dependents_count=2,
        inss_monthly=Decimal("200"),
        alimony_monthly=Decimal("300"),
        livro_caixa_expenses_monthly=Decimal("100"),
    )
    # dependent_deduction = 2 * 189.59 = 379.18
    # itemized_total = 200 + 379.18 + 300 + 100 = 979.18 > simplified 607.20 -> itemized wins
    assert r.deduction_path == "itemized"
    assert r.deductions_applied == Decimal("979.18")
    assert r.taxable_base == Decimal("2020.82")
    assert r.tax_due == Decimal("0.00")


def test_deductions_never_push_base_negative(carne_leao_table):
    r = _run(500, carne_leao_table, inss_monthly=Decimal("2000"))
    assert r.taxable_base == Decimal("0.00")
    assert r.tax_due == Decimal("0.00")


def test_zero_itemized_deductions_still_get_the_simplified_discount(carne_leao_table):
    """A freelancer who declares no INSS/dependents/alimony/livro-caixa at
    all is still automatically entitled to the flat simplified discount
    (CLAUDE.md never lets a real deduction go unclaimed by omission) --
    this is real, sourced Carne-Leao mechanics independent of Lei 15.270/2025.
    """
    r = _run(3036, carne_leao_table)  # no deduction kwargs => all zero itemized
    assert r.deduction_path == "simplified"
    assert r.deductions_applied == Decimal("607.20")


def test_itemized_wins_when_it_exceeds_the_simplified_discount(carne_leao_table):
    r = _run(6000, carne_leao_table, inss_monthly=Decimal("649.60"))
    assert r.deduction_path == "itemized"
    assert r.deductions_applied == Decimal("649.60")


def test_sliding_reduction_zero_above_upper_bound(carne_leao_table):
    r = _run(8000, carne_leao_table)
    # gross 8000 > upper_bound 7350 => no reduction at all, regardless of tax_before
    assert r.sliding_reduction_applied == Decimal("0")


def test_pre_2026_table_without_sliding_reduction_is_unaffected():
    legacy_table = {
        "effective_from": "2020-01-01",
        "source_url": "https://example.invalid/legacy",
        "verified_on": "2020-01-01",
        "verified": True,
        "dependent_deduction": 189.59,
        "simplified_discount_cap_monthly": 0,
        "brackets": [
            {"up_to": 1903.98, "rate": 0.0, "deduction": 0.0},
            {"up_to": None, "rate": 0.275, "deduction": 869.36},
        ],
    }
    r = _run(6000, legacy_table)
    assert r.sliding_reduction_applied == Decimal("0")
    assert r.sliding_reduction_verified is False


# ── Receita Federal's own worked examples ──────────────────────────────────
# gov.br "Exemplos de aplicacao da Lei 15.270/2025", fetched 2026-07-30 and
# reproduced here EXACTLY (all 5), as the permanent regression tests
# CLAUDE.md Section 8.1 requires. Each one exercises both mechanisms
# together: the simplified-vs-itemized deduction choice AND the sliding
# reduction, on real Receita-published numbers rather than hand-derived ones.

def test_receita_worked_example_1_alicota_zero(carne_leao_table):
    r = _run(3036.00, carne_leao_table)
    assert r.deduction_path == "simplified"
    assert r.deductions_applied == Decimal("607.20")
    assert r.taxable_base == Decimal("2428.80")
    assert r.tax_before_sliding_reduction == Decimal("0.00")
    assert r.tax_due == Decimal("0.00")


def test_receita_worked_example_2_renda_abaixo_5000(carne_leao_table):
    r = _run(4000.00, carne_leao_table)
    assert r.taxable_base == Decimal("3392.80")
    assert r.tax_before_sliding_reduction == Decimal("114.76")
    assert r.sliding_reduction_applied == Decimal("114.76")
    assert r.tax_due == Decimal("0.00")


def test_receita_worked_example_3_renda_5000(carne_leao_table):
    r = _run(5000.00, carne_leao_table)
    assert r.taxable_base == Decimal("4392.80")
    assert r.tax_before_sliding_reduction == Decimal("312.89")
    assert r.sliding_reduction_applied == Decimal("312.89")
    assert r.tax_due == Decimal("0.00")


def test_receita_worked_example_4_renda_6000_itemized_wins(carne_leao_table):
    r = _run(6000.00, carne_leao_table, inss_monthly=Decimal("649.60"))
    assert r.deduction_path == "itemized"
    assert r.taxable_base == Decimal("5350.40")
    assert r.tax_before_sliding_reduction == Decimal("562.63")
    assert r.sliding_reduction_applied == Decimal("179.75")
    assert r.tax_due == Decimal("382.88")


def test_receita_worked_example_5_renda_sem_reducao(carne_leao_table):
    r = _run(7607.20, carne_leao_table)
    assert r.taxable_base == Decimal("7000.00")
    assert r.tax_before_sliding_reduction == Decimal("1016.27")
    assert r.sliding_reduction_applied == Decimal("0.00")
    assert r.tax_due == Decimal("1016.27")
