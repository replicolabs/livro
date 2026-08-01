---
name: book_receipt
description: Fetch the official BACEN PTAX rate for a receipt date, compute the BRL value, and append the income-leg ledger entry
version: 0.1.0
author: livro
tags: [livro, ledger, bacen]
---

# Book receipt

Applied after `classify_receipt` for any leg that should actually be booked
as USDC income (CLAUDE.md Section 4.1, 6.1).

## What to do

1. **Fetch the BACEN PTAX quote window** via `http_request` against the
   Olinda API (`https://olinda.bcb.gov.br/olinda/service/PTAX/version/v1/odata/...`).
   Confirm the exact date-parameterized endpoint and query format from the
   live Olinda API docs at call time rather than guessing the query string
   (CLAUDE.md Section 6.1) -- fetch a window of a week or two ending on the
   receipt date so a weekend/holiday gap has quotes to fall back to.

2. **Resolve the fallback rule deterministically** -- pass the fetched
   quotes into the tax engine via `shell`:
   `echo '{"receipt_date": "...", "quotes": {...}}' | python3 -m tax_engine ptax_resolve`.
   This applies the documented most-recent-prior-business-day rule and
   reports whether it fired (`fallback_rule_applied`) rather than leaving
   that logic to be re-derived inline each time.

3. **Use the venda quote consistently.** This is a standing, documented
   decision (CLAUDE.md Section 6.1) -- do not switch between compra/venda
   from one booking to the next. If the freelancer or a reviewing
   accountant ever questions this choice, say plainly that it's the
   documented convention pending final confirmation of which quote type is
   legally correct for this specific conversion purpose (CLAUDE.md Section
   11's open items) -- don't present it as settled beyond doubt.

4. **Compute `brl_value = usdc_amount * fx_rate_used`** and append one
   `ledger_entry` (type: income) to `workspace/ledger/income.jsonl` with
   every field from CLAUDE.md Section 4.1 populated, including the full
   `fx_rate_used` object (source, endpoint queried, quote type, date of
   quote, fallback flag). Append only -- never edit or overwrite a past
   entry. A correction is a new entry that references what it corrects.

5. **Notify the freelancer** of the new booked receipt in their stored
   language. Read `language` from `workspace/config/user_preferences.json`
   (default `pt-BR`, per docs/language.md Section 1 -- never guessed from
   the message itself) and render the notification via `shell`:
   `echo '{"usdc_amount": "...", "client_label": "...", "receipt_date": "...", "ptax_rate": "...", "brl_value": "...", "language": "..."}' | python3 -m rendering payment_received`.
   Send the rendered `text` verbatim -- do not compose this message freehand
   in the model's own words, since the locale-correct decimal/thousands
   separators and the do-not-translate terms (`PTAX`, `BACEN`) are exactly
   what the rendering layer exists to guarantee (docs/language.md Sections
   4-5).
