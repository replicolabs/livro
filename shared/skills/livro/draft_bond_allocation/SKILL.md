---
name: draft_bond_allocation
description: Draft (never execute) an Etherfuse Tesouro allocation, only on explicit freelancer request
version: 0.1.0
author: livro
tags: [livro, etherfuse, bonds, custody]
---

# Draft bond allocation

Only triggered by an explicit, per-payment `allocate_bond` disposition
instruction (CLAUDE.md Sections 3.1, 4.2, 6.3, user story 7). Never
unprompted -- Livro does not suggest this path itself.

## What to do

1. Confirm the amount to allocate (the USDC leg this disposition instruction
   covers) and that the freelancer has already completed Etherfuse's KYC on
   their own account -- this is explicitly the freelancer's responsibility,
   never something Livro automates or holds credentials for (CLAUDE.md
   Section 6.3, non-goal Section 10).

2. Confirm current API/SDK access requirements directly from Etherfuse's
   docs at call time rather than assuming a specific integration shape from
   training data -- Etherfuse's integration surface is exactly the kind of
   external-service detail that can have changed since any prior knowledge
   of it.

3. Construct or request the unsigned allocation transaction (or a Blink/
   link, if Etherfuse exposes one). Livro's role stops at handing this back
   for the freelancer to review and sign -- never store Etherfuse
   credentials, never hold custody of the resulting position.

4. This allocation also triggers a `book_disposal` for the USDC leg being
   allocated (CLAUDE.md Section 3.1) -- apply the same weighted-average
   cost-basis and capital-gains logic as any other disposal via the tax
   engine's `capital_gains` command, since USDC is being disposed of in
   exchange for the bond position, even though no BRL conversion happens.

5. Create the `bond_position` record (CLAUDE.md Section 4.4) with
   `status: drafted` and `tax_treatment_flag: novel_asset_class_unresolved`
   always set to true for v1 -- **never compute a confident yield tax
   figure for the Tesouro product itself.** Its tax treatment (as distinct
   from the underlying real Tesouro Direto bond) is explicitly unresolved
   (CLAUDE.md Section 11); state what you know about the disposal leg, flag
   the yield-taxation gap explicitly, and point the freelancer to a
   contador for that specific question.

## Language

Read `language` from `workspace/config/user_preferences.json` (default
`pt-BR`, docs/language.md Section 1). No dedicated rendering-layer template
covers this skill's messages (docs/language.md Section 6 doesn't specify
one); compose the prose freehand in the stored language, format every
BRL/USDC figure and date via the rendering CLI's primitive formatters
(`python3 -m rendering format_brl` / `format_usdc` / `format_date`, see
`draft_refund`'s Language section for exact call shape) rather than inline
string building, and never translate `Contador` or any other term in
`rendering/rendering/terms.py`.
