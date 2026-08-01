"""CLAUDE.md Section 8.2's continuous-chain integration test, run for real
across the actual packages rather than described in prose:

    invoice created -> mocked payment detected -> income entry booked
    -> disposition instruction applied -> disposal entry booked, correct gain/loss

Every step below calls the SAME code a skill/SOP would invoke via `shell`
(tax_engine's ptax/cost_basis modules, ledger's validated record
dataclasses) -- this is not a reimplementation, it's those real modules
wired together end to end, with only the Solana RPC and BACEN PTAX network
calls mocked (CLAUDE.md Section 8.2: "mocked RPC/API... no live network in
tests"). It cannot prove the live LLM agent follows this sequence -- that
still needs a real run -- but it does prove the sequence is internally
consistent and that ledger's structural validation accepts exactly what
tax_engine produces, not just hand-crafted test fixtures.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from ledger.records import DisposalEntry, DispositionInstruction, FxRateUsed, IncomeEntry
from tax_engine.cost_basis import CostBasisPool
from tax_engine.ptax import resolve_ptax_rate


# ── Step 0: the invoice draft_invoice would have created ────────────────

INVOICE = {
    "reference_key": "RefKeyABC123",
    "receiving_address": "FreshAddrForThisInvoiceOnly",
    "expected_usdc": Decimal("800"),
    "client_label": "Berlin client",
}


# ── Step 1: mocked Solana RPC response, already "shaped down" per
# CLAUDE.md Section 6.2 (signature/amount/timestamp only -- never the raw
# getSignaturesForAddress payload reaching this far) ─────────────────────

def mock_get_signatures_for_address(reference_key: str) -> dict:
    assert reference_key == INVOICE["reference_key"]
    return {
        "signature": "5x7MockedSolanaSignatureForTestingOnly",
        "amount_usdc": Decimal("800"),
        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "block_time": datetime(2026, 7, 5, 14, 30, tzinfo=timezone.utc),
    }


# ── Step 2: mocked BACEN PTAX quote window (venda), a weekend gap
# deliberately present so ptax_resolve's real fallback logic is exercised ──

MOCK_PTAX_QUOTES = {
    date(2026, 7, 3): Decimal("5.4000"),  # Friday -- the fallback target
    # 2026-07-04/05 (Sat/Sun) have no published quote
}


def test_full_flow_exact_match_convert_to_brl():
    # Step 1: mocked payment detected
    tx = mock_get_signatures_for_address(INVOICE["reference_key"])
    assert tx["amount_usdc"] == INVOICE["expected_usdc"]  # classify_receipt: exact_match

    receipt_date = date(2026, 7, 5)  # Sunday -- forces the PTAX fallback rule

    # Step 2: income entry booked (real ptax_resolve, real fallback logic)
    resolution = resolve_ptax_rate(receipt_date, lambda d: MOCK_PTAX_QUOTES.get(d))
    assert resolution.fallback_rule_applied is True
    assert resolution.date_used == date(2026, 7, 3)

    brl_value = tx["amount_usdc"] * resolution.rate
    income_entry = IncomeEntry(
        entry_id="income-1",
        tx_signature=tx["signature"],
        reference_key=INVOICE["reference_key"],
        receiving_address=INVOICE["receiving_address"],
        client_label=INVOICE["client_label"],
        usdc_amount=tx["amount_usdc"],
        receipt_date=receipt_date,
        receipt_classification="exact_match",
        expected_amount=INVOICE["expected_usdc"],
        fx_rate=resolution.rate,
        fx_rate_used=FxRateUsed(
            source="BCB PTAX",
            endpoint_queried="https://olinda.bcb.gov.br/olinda/service/PTAX/version/v1/odata/...",
            quote_type=resolution.quote_type,
            date_of_quote=resolution.date_used,
            fallback_rule_applied=resolution.fallback_rule_applied,
        ),
        brl_value=brl_value,  # ledger.IncomeEntry's own __post_init__ re-derives and checks this
        created_at=datetime(2026, 7, 5, 15, 0),
    )
    assert income_entry.brl_value == Decimal("4320.00")  # 800 * 5.40

    # Step 3: disposition instruction applied (freelancer chose convert_to_brl)
    disposition = DispositionInstruction(
        entry_id="disp-1",
        linked_income_entry_id=income_entry.entry_id,
        instruction_source="explicit_per_payment",
        instruction="convert_to_brl",
        confirmed_by_user_at=datetime(2026, 7, 5, 15, 5),
    )
    assert disposition.instruction == "convert_to_brl"

    # Step 4: disposal entry booked, correct gain/loss -- real cost-basis pool
    pool = CostBasisPool()
    pool.add_income(income_entry.usdc_amount, income_entry.brl_value)

    # Converts same-day at a slightly different realized rate (a real BRL
    # on/off-ramp spread), so this exercises a genuine non-zero gain, not
    # just a same-number round-trip.
    realized_rate = Decimal("5.4250")
    proceeds = income_entry.usdc_amount * realized_rate
    disposal_result = pool.dispose(income_entry.usdc_amount, proceeds_brl=proceeds)

    disposal_entry = DisposalEntry(
        entry_id="disposal-1",
        linked_income_entry_ids=(income_entry.entry_id,),
        disposal_date=date(2026, 7, 5),
        disposal_reason="converted_to_brl",
        usdc_amount_disposed=disposal_result.usdc_amount_disposed,
        cost_basis_brl=disposal_result.cost_basis_brl,
        proceeds_brl=disposal_result.proceeds_brl,
        gain_or_loss_brl=disposal_result.gain_or_loss_brl,
        regime_applied="foreign_no_exemption",
        created_at=datetime(2026, 7, 5, 15, 10),
    )

    # cost basis = the full income entry's BRL value (100% disposed);
    # proceeds = 800 * 5.4250; gain = proceeds - cost_basis
    assert disposal_entry.cost_basis_brl == Decimal("4320.00")
    assert disposal_entry.proceeds_brl == Decimal("4340.00")
    assert disposal_entry.gain_or_loss_brl == Decimal("20.00")

    # Pool is fully drawn down -- nothing left held after a 100% disposal.
    assert pool.total_usdc_held == Decimal("0")
    assert pool.total_cost_basis_brl == Decimal("0")


def test_full_flow_hold_as_usdc_produces_no_disposal_entry():
    """The other branch of watch_payment Step 4: 'If hold_as_usdc, do
    nothing further -- the cost basis carries forward untouched.' No
    DisposalEntry should exist at all in this path.
    """
    tx = mock_get_signatures_for_address(INVOICE["reference_key"])
    receipt_date = date(2026, 7, 3)  # a date with a directly-published quote

    resolution = resolve_ptax_rate(receipt_date, lambda d: MOCK_PTAX_QUOTES.get(d))
    assert resolution.fallback_rule_applied is False

    income_entry = IncomeEntry(
        entry_id="income-2",
        tx_signature=tx["signature"],
        reference_key=INVOICE["reference_key"],
        receiving_address=INVOICE["receiving_address"],
        client_label=INVOICE["client_label"],
        usdc_amount=tx["amount_usdc"],
        receipt_date=receipt_date,
        receipt_classification="exact_match",
        expected_amount=INVOICE["expected_usdc"],
        fx_rate=resolution.rate,
        fx_rate_used=FxRateUsed(
            source="BCB PTAX",
            endpoint_queried="https://olinda.bcb.gov.br/...",
            quote_type=resolution.quote_type,
            date_of_quote=resolution.date_used,
            fallback_rule_applied=False,
        ),
        brl_value=tx["amount_usdc"] * resolution.rate,
        created_at=datetime(2026, 7, 3, 10, 0),
    )

    disposition = DispositionInstruction(
        entry_id="disp-2",
        linked_income_entry_id=income_entry.entry_id,
        instruction_source="standing_preference",
        instruction="hold_as_usdc",
        confirmed_by_user_at=datetime(2026, 7, 3, 10, 1),
    )

    pool = CostBasisPool()
    pool.add_income(income_entry.usdc_amount, income_entry.brl_value)

    # hold_as_usdc: cost basis carries forward, nothing disposed, no
    # DisposalEntry constructed at all in this branch.
    assert disposition.instruction == "hold_as_usdc"
    assert pool.total_usdc_held == income_entry.usdc_amount
    assert pool.total_cost_basis_brl == income_entry.brl_value
