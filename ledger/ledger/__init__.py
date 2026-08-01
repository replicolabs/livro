"""Structural validation for Livro's append-only ledger records.

CLAUDE.md Section 7's custody checklist: "Every fund-adjacent action...
requires an explicit, timestamped user confirmation captured in the record
itself -- the code should make it structurally awkward to create one of
these records without that field populated." Before this package existed,
that requirement was enforced only by prose in the skill files -- an agent
following a buggy prompt could still construct an invalid record. Every
dataclass here raises immediately (`__post_init__`) on construction if a
required confirmation timestamp is missing, of the wrong type, or if a
derived figure (a BRL value, a gain/loss) doesn't actually match its stated
inputs -- CLAUDE.md Section 1.5's "every number has a receipt" rule,
enforced as a runtime invariant, not just a review checklist item.

This package validates and serializes; it does not decide business logic
(that's tax_engine) or reach into the filesystem itself (that's the calling
skill, via file_write, same separation as tax_engine/rendering/trust).
"""
