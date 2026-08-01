# watch_payment

Polls every open invoice's Solana Pay reference key for a payment, classifies
what arrived against what was expected, books the income leg with the correct
BACEN PTAX rate, and captures the freelancer's disposition instruction
(convert / hold / allocate) -- never assuming it. See CLAUDE.md Sections 1.2,
3.1, 4.1-4.2, 4.6, 6.1-6.2 for the full data model and non-negotiable
principles this SOP must uphold.

## Steps

1. **Poll open invoices** -- Read `workspace/ledger/income.jsonl` and any
   open-invoice tracking file to find invoices with no matching income entry
   yet. For each, call Solana RPC `getSignaturesForAddress` on its
   `reference_key`. Shape the RPC response down before reasoning over it:
   extract only signature, amount, token mint, and block time for any new
   transaction -- never pass the raw response through (CLAUDE.md Section
   6.2). Note which invoices are past their retention window per
   `payment_exception.late_after_expiry` handling (Section 4.6) -- keep
   polling them anyway; do not stop just because an invoice looks "expired".
   - tools: http_request, file_read

2. **Classify and book each new receipt** -- Apply the `classify_receipt`
   skill's rules: exact match, overpayment, underpayment, wrong asset, or
   late-after-expiry (CLAUDE.md Section 4.6). For anything other than an
   exact match, create a `payment_exception` record
   (`resolution_status: pending_freelancer_decision`) and notify the
   freelancer distinctly -- never silently run a wrong-asset or mismatched
   receipt through the standard USDC/BACEN booking path. For a valid USDC
   receipt (exact match, overpayment's matched portion, or a late payment
   still within retention), apply the `book_receipt` skill: fetch the BACEN
   PTAX rate for the receipt date via `http_request`
   (`ptax_resolve` fallback logic lives in the tax engine -- invoke it via
   `shell` with the fetched quote window rather than re-deriving the
   weekend/holiday fallback rule inline), compute the BRL value, and append
   the `ledger_entry` (income leg) to `workspace/ledger/income.jsonl`.
   Never overwrite or edit a past entry -- append only.
   - tools: http_request, shell, file_read, file_write

3. **Determine disposition** -- Read `workspace/config/user_preferences.json`
   for both `standing_disposition_preference` and `language` (docs/language.md
   Section 1 -- default `pt-BR`, never guessed). If a standing preference
   exists, apply it. If not, get the choice labels in the freelancer's
   language via `shell`: `echo '{"language": "..."}' | python3 -m rendering disposition_choices`,
   then call `ask_user` with those three `choices`. Never pick a disposition
   yourself absent one of these two sources (CLAUDE.md Section 1.2). Append a
   `disposition_instruction` record to
   `workspace/ledger/disposition_instructions.jsonl` with
   `confirmed_by_user_at` set to the actual confirmation timestamp -- never
   create this record with that field null or synthesized.
   - tools: file_read, shell, ask_user, file_write

4. **Book the disposal leg if the instruction requires one** -- If the
   instruction is `convert_to_brl`, invoke the tax engine's
   `cost_basis_dispose` command via `shell` with this user's full
   `income.jsonl` and `disposals.jsonl` history (chronological replay,
   CLAUDE.md Section 5.3) to compute the weighted-average cost basis and
   gain/loss, then append the disposal `ledger_entry` to
   `workspace/ledger/disposals.jsonl`. If `allocate_bond`, hand off to the
   `draft_bond_allocation` skill instead (never execute an allocation from
   inside this SOP). If `hold_as_usdc`, do nothing further -- the cost basis
   carries forward untouched.
   - tools: shell, file_write
