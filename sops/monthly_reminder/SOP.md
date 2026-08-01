# monthly_reminder

Fires daily; on all but the configured lead-days-before-month-end, it is a
no-op. On the right day, it computes this month's Carne-Leao liability and
proactively reminds the freelancer, including the standing prompt for
income Livro cannot observe on its own (CLAUDE.md Sections 1.8, 3.1, 5.1,
4.9's `reminder_lead_days`).

## Steps

1. **Check whether today is the reminder day** -- Read
   `workspace/config/user_preferences.json` for `reminder_lead_days`
   (default 5). Run a one-line date computation via `shell`
   (e.g. `python3 -c "..."`) to get the number of calendar days remaining
   until the last day of the current month. If it does not equal
   `reminder_lead_days`, end the run here without sending anything -- do
   not send a reminder on the wrong day.
   - tools: shell, file_read
   - on_failure: fail

2. **Compute this month's Carne-Leao figure** -- Sum this calendar month's
   entries in `workspace/ledger/income.jsonl` (`brl_value`), including any
   `external_holding` entries declared this month, and read this month's
   deductions from `user_preferences.json`. Invoke the tax engine via
   `shell`: `echo '{...}' | python3 -m tax_engine carne_leao` (see
   `tax_engine/tax_engine/cli.py`). Note in the result which portion of the
   base came from directly-observed ledger entries versus
   `provenance: declared_by_user` external holdings (CLAUDE.md Section 4.8).
   - tools: file_read, shell

3. **Send the proactive reminder and ask about other income** -- Read
   `language` from `user_preferences.json` (default `pt-BR`, docs/language.md
   Section 1 -- this scheduled message must honor the stored preference
   exactly like any reply, never silently defaulting: Section 8 item 7).
   Render the summary via `shell`:
   `echo '{"base": "...", "bracket_rate": "...", "tax_due": "...", "darf_code": "0190", "competencia_month": N, "competencia_year": YYYY, "vencimento": "YYYY-MM-DD", "language": "..."}' | python3 -m rendering carne_leao_summary`.
   This one rendered message already includes the DARF code, competencia,
   vencimento, tax due, the disclaimer, and the "any other income?" prompt
   (docs/language.md Section 6) -- send its `text` verbatim via `ask_user`
   rather than composing an equivalent message freehand, and note
   separately (before rendering, in your own step reasoning) if any part of
   the base rests on user-declared rather than directly-observed income
   (CLAUDE.md Section 1.8), appending that distinction as plain text before
   or after the rendered summary. If the freelancer names other income in
   reply, apply the `register_external_holding` skill before ending the run.
   - tools: file_read, shell, ask_user, file_write
