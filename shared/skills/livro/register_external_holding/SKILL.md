---
name: register_external_holding
description: Let the freelancer declare USDC or income Livro can't see directly, folding it into the same cost-basis pool and tax figures
version: 0.1.0
author: livro
tags: [livro, ledger, external]
---

# Register external holding

Triggered on request, or in response to `monthly_reminder`'s proactive
"any other income this month?" prompt (CLAUDE.md Section 4.8, user stories
13-14).

## What to do

1. Ask for whatever the freelancer knows: asset (USDC, another crypto, or
   fiat income), amount, and an approximate receipt date. Accept
   "I don't know the exact date" -- this is explicitly an estimate path, not
   a precise one.

2. If the freelancer knows the rate/value at receipt, use it. Otherwise,
   look up the BACEN PTAX rate for the approximate date (same fallback rule
   as `book_receipt`) and **clearly flag the resulting BRL value as an
   estimate** in the record's `notes` field -- do not present it with the
   same confidence as a directly-observed on-chain receipt.

3. Append an `external_holding` record (CLAUDE.md Section 4.8) with
   `provenance: declared_by_user` always set -- this is what distinguishes
   it from entries Livro verified on-chain itself.

4. Fold it into the same weighted-average cost-basis pool as directly-
   observed income (via the tax engine's `cost_basis_dispose`/replay path,
   passing this entry alongside the on-chain ones) and into the same
   monthly income figure `monthly_reminder` computes.

5. **Every downstream output that uses this contribution must be able to
   show which portion came from direct observation versus declaration**
   (CLAUDE.md Section 1.8) -- when summarizing a month's income or a year's
   totals, say plainly "R$X observed on-chain, R$Y declared by you" rather
   than blending them into one unlabeled figure. This is what keeps the
   "quiet disclaimer + optional completeness" design honest rather than
   cosmetic.

## Language

This is a proactive prompt as well as a conversational intake. When
initiating it yourself (rather than replying to a message that already
triggered it), read `language` from `workspace/config/user_preferences.json`
(default `pt-BR`, docs/language.md Section 1) and render the standalone
prompt via `shell`: `echo '{"language": "..."}' | python3 -m rendering external_holding_prompt`.
Any BRL/date figures you report back after registering the holding go
through the same `python3 -m rendering` formatting as every other output --
never format a number inline by hand.
