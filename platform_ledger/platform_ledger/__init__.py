"""Cross-tenant billing/provisioning records for Livro's multi-tenant gate.

Deliberately separate from `ledger/` (which is strictly a freelancer's own
tax-relevant records) -- mixing platform billing objects into that package
would blur a boundary that matters: a tenant's own income/disposal ledger is
never touched by anything here. This package imports `ledger.records`'s own
validation helpers (`_q`, `_require_datetime`, `_require_derivation`) rather
than duplicating the arithmetic-identity logic, so the two stay drift-free.

See the multi-tenant plan (docs/language.md-adjacent design note, or the
approved plan at /home/dav/.claude/plans/immutable-wiggling-pearl.md) for
the full architecture this package is one piece of.
"""
