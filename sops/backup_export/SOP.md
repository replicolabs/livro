# backup_export

Weekly, serializes the ledger to a portable snapshot and delivers it
somewhere the freelancer controls, not just this one device (CLAUDE.md
Sections 1's implicit self-hosted-completeness concern, 3.1, and 9's
"Backup export artifact" deliverable).

Primary delivery path is a `git` push to a private remote the freelancer
owns, chosen over an email attachment because it needs no extra channel
config, works with the stock `shell` tool alone, and gives the freelancer a
full, diffable history of every past backup rather than just the latest one.
An email-attachment alternative (via a configured email channel) is
documented in `SETUP.md` for freelancers who prefer that instead -- this SOP
does not attempt to invent a generic outbound-email-with-attachment
mechanism where none exists as a built-in tool.

## Steps

1. **Bundle the ledger** -- Run, via `shell`, a timestamped archive of
   `workspace/ledger/`, `workspace/config/`, and `tax_engine/tax_tables/`
   (the dated tax tables are part of what makes any given figure
   reproducible later) into `workspace/backups/livro-backup-<YYYY-MM-DD>.tar.gz`.
   - tools: shell

2. **Push to the freelancer's private remote** -- Run, via `shell`,
   `git add`, `git commit`, and `git push` inside the configured private
   backup repository path (set once during setup; see `SETUP.md`). If the
   push fails (no network, remote rejected, auth expired), do not silently
   drop the backup -- keep the local archive and escalate.
   - tools: shell
   - on_failure: retry:1

3. **Confirm with the freelancer** -- Read `language` from
   `workspace/config/user_preferences.json` (default `pt-BR`,
   docs/language.md Section 1) before composing the notification -- this is
   a scheduled/proactive message, exactly the kind Section 3 requires to
   honor the stored preference rather than defaulting silently. No
   dedicated rendering-layer template covers this message; compose it
   freehand in the stored language. Notify success or failure via
   `ask_user`/`escalate_to_human` respectively. On repeated failure across
   multiple weekly runs, escalate at `urgency: "high"` -- an unbacked-up
   ledger is exactly the risk this SOP exists to prevent.
   - tools: file_read, ask_user, escalate_to_human
