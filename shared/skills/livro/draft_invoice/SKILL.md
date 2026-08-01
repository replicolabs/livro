---
name: draft_invoice
description: Build a fresh-address Solana Pay invoice link and draft invoice text for a freelancer's foreign client
version: 0.1.0
author: livro
tags: [livro, invoicing, solana-pay]
---

# Draft invoice

Use this when the freelancer asks to invoice a client in USDC (e.g. "invoice
the Berlin client for 500 USDC").

## What to do

1. **Never reuse a receiving address across invoices** (CLAUDE.md Section
   3.1/6.2 and user story 10). Ask the freelancer's wallet to derive a fresh
   receiving address for this invoice specifically -- Livro tracks which
   address belongs to which invoice; it never generates or holds the keys
   behind them. If the freelancer hasn't set up per-invoice address
   derivation in their wallet, explain why it matters (a reused address
   lets any client look up their full income history from other clients on
   a public block explorer) before proceeding.

2. Generate a Solana Pay reference key (a fresh keypair's public key used
   only for payment correlation, not signing) for this invoice.

3. Build the standard Solana Pay transfer-request URL:
   `solana:<recipient>?amount=<amount>&spl-token=<USDC mint>&reference=<reference_key>`.
   Confirm the current mainnet USDC mint address from the freelancer's
   configured RPC/token list rather than hardcoding one from memory --
   mint addresses are exactly the kind of fact that should come from
   config, not training data.

4. Draft plain invoice text: amount, client label, payment link, and a
   plain-language fallback line for a client who doesn't already hold USDC
   (CLAUDE.md Section 10 -- Livro does not automate client-side acquisition,
   just explains it in one line).

5. Record the pending invoice (expected amount, reference key, receiving
   address, client label, creation timestamp) so `watch_payment` can match
   an incoming transaction against it later. Do not create the
   `ledger_entry` yet -- that only happens once a payment actually arrives
   (see `classify_receipt` and `book_receipt`).

6. Hand the freelancer the payment link and draft invoice text to send to
   their client themselves. Livro never contacts the client directly. Read
   `language` from `workspace/config/user_preferences.json` (default
   `pt-BR`, docs/language.md Section 1) and render the confirmation message
   via `shell`: `echo '{"usdc_amount": "...", "client_label": "...", "month": N, "link": "...", "language": "..."}' | python3 -m rendering invoice_draft`.
   Send the rendered `text` verbatim rather than composing it freehand.
