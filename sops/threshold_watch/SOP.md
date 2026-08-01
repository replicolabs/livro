# threshold_watch

Checks cumulative monthly transaction volume (income + disposal legs) against
the IN 1888 / DeCripto self-report threshold and proactively flags it before
it is crossed, not only after (CLAUDE.md Section 5.5). Runs every 6 hours via
`cron` rather than on every ledger write: the threshold moves gradually
across a month, so a filesystem-trigger-per-write (also a real, wired option
per `docs/book/src/sop/fan-in/filesystem.md`) was considered and rejected as
unnecessary added complexity for this specific check -- a 6-hour cron cadence
still catches the "approaching" flag comfortably before the threshold is hit
in realistic usage.

## Steps

1. **Sum this month's volume** -- Read every entry in
   `workspace/ledger/income.jsonl` and `workspace/ledger/disposals.jsonl`
   dated in the current calendar month, and sum their BRL-value fields
   (`brl_value` for income, `proceeds_brl` for disposals) into one
   cumulative figure.
   - tools: file_read

2. **Check against the threshold** -- Invoke the tax engine via `shell`:
   `echo '{"cumulative_volume_brl": "..."}' | python3 -m tax_engine threshold_watch`.
   If the result's `approaching` field is true and no flag has already been
   sent this calendar month for this threshold crossing, read `language`
   from `workspace/config/user_preferences.json` (default `pt-BR`,
   docs/language.md Section 1) and render the warning via `shell`:
   `echo '{"threshold_brl": "...", "language": "..."}' | python3 -m rendering threshold_warning`.
   Send the rendered `text` via `ask_user` (a status update; no reply is
   required, but `ask_user` is the available channel-send mechanism),
   appended with the table's `table_verified` status and caveat verbatim --
   this specific figure (R$35,000/month, per
   `tax_tables/in1888_threshold_2026.json`) is flagged unverified pending
   primary-source confirmation, and the freelancer should know that when
   deciding how much weight to put on it. If `exceeded` is true, escalate
   with `escalate_to_human` at `urgency: "high"` instead of the routine flag
   (compose that escalation in the same stored language, though
   `escalate_to_human` has no dedicated rendering-layer template of its own
   -- follow the same term-preservation and number-formatting discipline by
   hand: never translate `IN 1888`, format any figure via
   `python3 -m rendering` rather than composing it inline).
   - tools: file_read, shell, ask_user, escalate_to_human, file_write
