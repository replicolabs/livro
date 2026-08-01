"""The gate: sits between Meta's one WhatsApp Cloud API webhook Callback URL
and ZeroClaw's per-tenant internal aliases.

Meta allows exactly one Callback URL per WhatsApp Business number/App --
it has no concept of tenants and cannot fan out to different URLs per
sender. ZeroClaw's per-alias routing (`/whatsapp/{alias}`) was built for
multiple *distinct* phone numbers, not multiple tenants sharing one number.
So tenant routing has to be this service's job, done by rewriting the
destination path (`/whatsapp/{tenant_id}`) before forwarding to ZeroClaw's
loopback-only gateway -- Meta itself never learns tenants exist.

This also happens to satisfy the credit-gating requirement: a hard
spend-prevention check must run *before* any ZeroClaw agent turn starts,
since a mid-turn approval check can't undo an LLM call that already
happened. Sitting in front of the webhook is the only point early enough.

See /home/dav/.claude/plans/immutable-wiggling-pearl.md for the full design.
"""
