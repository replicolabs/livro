---
name: annual_summary
description: Roll up a full year's ledger for DIRPF prep -- income totals, gains/losses, and year-end holdings at cost
version: 0.1.0
author: livro
tags: [livro, dirpf, annual]
---

# Annual summary

Triggered on request (CLAUDE.md Section 3.1, user story 9).

## What to do

1. **Ordinary income total** -- sum every income-leg `ledger_entry` for the
   requested year, split by directly-observed vs `declared_by_user`
   provenance (Section 1.8/4.8), for cross-checking against the twelve
   Carnê-Leão computations already booked.

2. **Capital gains/losses** -- sum every disposal-leg `ledger_entry` for the
   year. Report gains and losses separately and plainly -- never net a loss
   against a gain in this summary without the same `loss_offset_flag:
   requires_accountant_confirmation` the tax engine already attaches to
   every loss (Section 5.2). This summary presents facts; it does not
   decide the offset question for the freelancer.

3. **Year-end holdings at cost** -- read the current weighted-average
   cost-basis pool state (replay `income.jsonl` + `disposals.jsonl`
   chronologically through the tax engine's cost-basis replay path) as of
   December 31. Report **cost basis, not market value** (CLAUDE.md Section
   5.4) -- this is the figure Bens e Direitos actually wants, and reporting
   market value instead is explicitly flagged as a common, serious mistake
   to avoid.

4. **Bens e Direitos threshold check** -- if the year-end cost basis is at
   or above the configured `single_asset_cost_basis_threshold_brl`
   (`tax_tables/bens_e_direitos_threshold_2026.json`), say so explicitly and
   name the asset group/subcategory/code from that table, flagging the
   asset code's own lower confidence (`asset_code_verified: false`) rather
   than stating it as certain.

5. Every figure in this summary carries the same one-line disclaimer
   (Section 1.7) and the scoped-visibility note (Section 1.8) -- this is a
   computation aid drawn only from what Livro has observed or the
   freelancer has declared, not an official filing, and not necessarily
   their complete financial picture unless they've declared everything
   external too.

## Language

Read `language` from `workspace/config/user_preferences.json` (default
`pt-BR`, docs/language.md Section 1). No dedicated rendering-layer template
covers a full annual summary (docs/language.md Section 6 doesn't specify
one); compose the prose freehand in the stored language, format every
BRL figure and date via the rendering CLI's primitive formatters
(`python3 -m rendering format_brl` -- pass `"signed": true` for any loss
figure so it never reads as a bare, easy-to-miss minus sign -- and
`format_date`), and never translate `Bens e Direitos`, `DIRPF`, `Carnê-Leão`,
or any other term in `rendering/rendering/terms.py`.
