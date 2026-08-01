---
name: export_for_contador
description: Export the ledger as three sheets shaped to mirror Receita's own Carne-Leao Web and GCAP tools, ready for a contador
version: 0.1.0
author: livro
tags: [livro, export, contador]
---

# Export for contador

Triggered on request (CLAUDE.md Section 3.1/5.6, user story 16). This is a
formatted **view over the ledger**, not a second source of truth -- every row
carries the same provenance and rate-source fields already in the ledger.

## What to do

1. **Sheet 1, Carnê-Leão-shaped** -- one row per income-leg entry: date,
   amount in USDC, exchange rate used (with source and quote type), amount
   in BRL, source/client label, and that month's deductions applied. Order
   by date within each month.

2. **Sheet 2, GCAP-shaped (capital gains)** -- one row per disposal-leg
   entry: disposal date, asset, cost basis, proceeds, gain or loss, and the
   regime applied (`foreign_no_exemption`, per
   `tax_tables/capital_gains_2026.json`). Never merge or net rows here --
   one row per disposal, exactly as booked.

3. **Sheet 3, holdings-at-year-end (Bens e Direitos)** -- asset, cost basis
   (never market value, per the same rule as `annual_summary`), and
   provenance (observed vs. declared) for every holding still open as of
   the requested year-end.

4. Write the export to the workspace (e.g.
   `workspace/exports/livro-export-<year>.csv` or similar, one file or
   sheet per section) so the freelancer can hand it directly to their
   contador, or open it themselves next to Receita's own Carnê-Leão Web and
   GCAP tools for direct comparison.

5. Include, once at the top of the export (not repeated per-row), the same
   disclaimer and scoped-visibility note as every other tax output (Sections
   1.7-1.8) plus a line naming which dated table versions were used for the
   figures inside (Carnê-Leão table, capital-gains table, effective_from and
   verified status of each) -- a contador reviewing this should be able to
   tell exactly which sourced config produced each number.

## Language

This export's own sheet headers and field labels stay in **Portuguese
regardless of the freelancer's chat language preference** -- docs/language.md
never states this explicitly (its scope is chat messages), but this export
is deliberately "shaped to mirror Receita's own Carnê-Leão Web and GCAP
tools" (Section 15.6/5.6), which are themselves Portuguese-language
government tools a Brazilian contador expects; translating the sheet's own
column headers would work against the export's stated purpose. This is a
considered extension of the do-not-translate spirit (docs/language.md
Section 4), not a silent assumption -- flag it to the freelancer if they ask
for an English-language export instead, rather than guessing which they
want. The **chat message that hands the export over**, by contrast, does
follow the stored `language` preference from
`workspace/config/user_preferences.json` like any other reply -- format any
BRL/date figures mentioned in that handover message via the rendering CLI's
primitive formatters, not inline.
