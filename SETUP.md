# Setting up Livro

Written so a stranger can reproduce this in an evening. Read `CLAUDE.md` (the
build blueprint) and `DEVIATIONS.md` (where reality diverged from it) first
if you want the reasoning behind these choices, not just the steps.

## 0. Prerequisites

- A ZeroClaw release binary (stock, no compiled plugins -- this is a Tier 1
  build). Standard pre-built binaries include WhatsApp Web support; confirm
  with `zeroclaw --version` / `zeroclaw channel doctor` after install.
- Python 3.10+ for the tax engine (`tax_engine/`).
- A Solana RPC endpoint you control or trust (a paid RPC is recommended over
  the public mainnet endpoint for reliability -- `watch_payment` polls it
  every 5 minutes).
- A private git remote you control, for `backup_export` (e.g. a private
  GitHub/Gitea repo, or any host reachable over `git push`).
- Your own WhatsApp (personal number) for Web-mode pairing, or a Telegram bot
  token from @BotFather as the documented fallback.

## 1. Tax engine: install and verify

```sh
cd tax_engine
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

All tests should pass. **Before relying on any figure for a real filing**,
read every `tax_tables/*.json` file's `verified` and `verification_caveat`
fields. Several figures were researched from primary sources (Receita
Federal's own published tables, the actual law text) and are `verified:
true`; a few — the exact IN 1888/DeCripto threshold, the offshore
capital-gains exemption carve-out, and a genuine unresolved discontinuity in
the new Lei 15.270/2025 sliding-reduction formula — are explicitly flagged
`verified: false` with a caveat explaining exactly what's uncertain and why.
Get a contador to confirm those specific points before this computes a real
DARF for you. See `DEVIATIONS.md` and the caveats themselves for details.

## 1b. Rendering engine (bilingual messages): install and verify

```sh
cd rendering
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

All tests should pass. This is the pt-BR/English message-rendering layer
described in `docs/language.md` — Livro replies in Brazilian Portuguese by
default for every new user, switches to English only on an explicit request
(never inferred), and never translates official terms like `Carnê-Leão`,
`DARF`, or `PTAX`. It is fully separate from the tax engine: it never
computes a figure, only formats one that was already computed. See
`DEVIATIONS.md` Section 5d for the one place this repo's rendering
deliberately diverges from `docs/language.md`'s own illustrative example (an
ambiguous bare-numerals English date) in favor of that same document's
explicit formatting rule.

## 1c. Trust guard (fund-moving-instruction detection): install and verify

```sh
cd trust
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

All tests should pass, including `tests/test_guard.py`'s automated
reproduction of the CLAUDE.md Section 7 prompt-injection scenario (a
redirect instruction embedded in a transaction memo / framed as coming from
the client / embedded in webhook content — all refused; the identical
wording from the freelancer's own authenticated chat — allowed). This
package is a deterministic pre-check `classify_receipt` calls via `shell`
before reasoning about any transaction memo or on-chain message content; it
cannot replace running the actual live-agent injection test and capturing a
transcript (Section 6 below) — that's still required — but it does pin the
one part of this defense that's pure code.

## 1d. Ledger record validation: install and verify

```sh
cd ledger
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

All tests should pass. This package makes it structurally impossible to
construct an invalid `disposition_instruction`, `refund_draft`,
`bond_position`, or other ledger record — a missing confirmation timestamp,
a wrong type, or a `brl_value`/`gain_or_loss_brl` that doesn't match its own
stated inputs all raise at construction time (CLAUDE.md Section 7's "make it
structurally awkward" requirement, and Section 1.5's "every number has a
receipt" rule, both enforced as runtime invariants). Skills validate a
record via `shell` (`python3 -m ledger validate`) before appending it to the
workspace JSONL ledger.

## 1e. Cross-package integration test: install and verify

```sh
cd integration_tests
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

This is CLAUDE.md Section 8.2's continuous-chain test — invoice → mocked
Solana RPC payment → validated `IncomeEntry` → `DispositionInstruction` →
validated `DisposalEntry` — run for real across `tax_engine` and `ledger`
together (only the Solana RPC and BACEN PTAX calls are mocked), not just
described in prose.

## 1f. Multi-tenant packages (platform_ledger + gate): install and verify

Optional — only needed if you're standing up the multi-tenant deployment
(Section 8 below), not the single-freelancer build above.

```sh
cd platform_ledger
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q

cd ../gate
python3 -m venv .venv
.venv/bin/pip install -e . pytest pytest-asyncio
.venv/bin/python -m pytest -q
```

`gate/tests/test_forwarding.py` is the highest-risk test in this whole
package — it proves the gate forwards Meta's webhook body byte-for-byte,
which is what lets ZeroClaw's own HMAC signature check succeed downstream.
See the approved plan at the time of writing
(`/home/dav/.claude/plans/immutable-wiggling-pearl.md` on the machine this
was built on — copy its contents into this repo if you want the full
multi-tenant design rationale preserved outside that machine-local path).

## 2. ZeroClaw install and workspace

Follow ZeroClaw's own install docs for your OS (`docs/book/src/setup/`) if
you don't already have it running. Then:

```sh
zeroclaw config set  # or edit config.toml directly -- see config/config.toml.example
```

Copy this repo's `sops/` and `shared/skills/livro/` into your ZeroClaw
install so the paths in `config/config.toml.example` (`sop.sops_dir`,
`skill_bundles.livro.directory`) resolve, or point those config fields at
this repo's paths directly if you're running ZeroClaw with
`ZEROCLAW_CONFIG_DIR` set to (or symlinked into) this repo.

**Use an absolute path for `sop.sops_dir`.** Confirmed live (`DEVIATIONS.md`
Section 9): unlike `skill_bundles.<alias>.directory`, an explicitly-set
`sop.sops_dir` resolves relative to the current working directory at the
moment each `zeroclaw` command runs, not the install root — `zeroclaw sop
validate` silently finds zero SOPs if run from anywhere other than the exact
directory you happened to set it relative to. After copying, verify with:

```sh
cd /tmp && zeroclaw sop validate   # run from an unrelated directory on purpose
```

All 4 SOPs (`watch_payment`, `monthly_reminder`, `threshold_watch`,
`backup_export`) should validate regardless of where you ran that from.

Copy the two workspace config templates into the agent's actual workspace
once it exists (`<install>/agents/livro/workspace/config/` by default, or
wherever `agents.livro.workspace` resolves):

```sh
mkdir -p <workspace>/config <workspace>/ledger <workspace>/backups
cp config/app_settings.json.example <workspace>/config/app_settings.json
cp config/user_preferences.json.example <workspace>/config/user_preferences.json
```

Edit both with your real Solana RPC URL, USDC mint (confirm it's still
current), backup git remote, and initial deductions. Leave
`standing_disposition_preference` as `null` unless you already know you want
every payment handled the same way -- the whole point is Livro asks instead
of assuming (CLAUDE.md Section 1.2).

## 3. Wire the channel

**WhatsApp Web (primary, recommended)**: set `channels.whatsapp.default.session_path`
to a persistent path, `enabled = true`, start the channel
(`zeroclaw channel start` or `zeroclaw daemon`), and scan the printed QR code
(or use `pair_phone` for pair-code linking) from the WhatsApp account you
want Livro to run under. Keep the session path on persistent storage --
losing it forces a fresh device link.

**Telegram (documented fallback)**: if WhatsApp Web pairing proves unstable,
set `channels.telegram.default.bot_token` (via the masked `config set`
prompt, never pasted into the file), `enabled = true`, add
`telegram.default` to `agents.livro.channels`, start the channel, and follow
the `/bind <code>` pairing flow from your own Telegram account (see
`docs/book/src/channels/telegram.md`). No public URL needed either way.

## 4. Set up the private backup remote

Create a private git repository you control (any host). Clone it somewhere
`backup_export`'s `shell` steps can reach, configure push credentials once
(SSH key or credential helper -- outside ZeroClaw's config, on the host
itself), and set `backup_git_remote` in `app_settings.json` to match. Run
the SOP once manually to confirm the push actually works before trusting the
weekly schedule:

```sh
zeroclaw sop validate backup_export
zeroclaw sop show backup_export
```

(There is no `zeroclaw sop run` -- trigger a one-off test via the agent's
`sop_execute` tool in a CLI session, or just wait for the Sunday 08:00 cron
trigger.)

**Alternative**: if you'd rather receive the backup by email instead of a
git push, configure an email channel (`docs/book/src/channels/email.md`) and
adapt `sops/backup_export/SOP.md` Step 2 to send the archive as an
attachment through it. This repo ships the git-push path by default because
it needs no extra channel config -- see `sops/backup_export/SOP.md`'s own
header note.

## 5. Validate everything

```sh
zeroclaw sop validate
zeroclaw sop list
zeroclaw skills list --agent livro
zeroclaw channel doctor
```

Fix any warning before going further -- a missing-steps or dangling-reference
warning means a run would fail at execution time, not just at review time.

## 6. Run the prompt-injection test (required submission artifact)

`trust/tests/test_guard.py` already proves the deterministic detection layer
refuses the CLAUDE.md Section 7 scenario in isolation (run `cd trust &&
.venv/bin/python -m pytest -q tests/test_guard.py -v` to see each case named
and passing). That is necessary but not sufficient -- it doesn't prove the
live agent actually calls the guard and honors its verdict mid-conversation.

Before trusting this with real money, confirm the refusal behavior holds
end-to-end on a running instance: send (or simulate) a message framed as
coming from a client, or embed an instruction in a transaction memo field,
that tries to get Livro to redirect a payment, change a disposition
instruction, or treat unverified input as the freelancer's own confirmed
intent. Confirm it's refused and logged (see `classify_receipt`'s "what
never happens here" section, which is the skill instruction telling the
agent to call `trust`'s guard in the first place). Capture the transcript
under `transcripts/` -- this is a required deliverable (CLAUDE.md Section
9.4), not optional polish, and it's the part the automated test above
cannot substitute for.

## 7. First real invoice

Message the agent: "invoice \<client\> for \<amount\> USDC." Confirm your
wallet derives a fresh receiving address (don't reuse one across invoices --
see `draft_invoice`), send the resulting link to a test client (or pay it
yourself from another wallet for the devnet/small-mainnet-amount dry run in
CLAUDE.md Section 8.3), and watch `watch_payment` pick it up on its next
5-minute poll.

## 8. Multi-tenant deployment (optional expansion, not part of the base bounty build)

Everything above is the single-freelancer product. This section stands up
the separate multi-tenant expansion: any freelancer messages one shared
WhatsApp Business number and gets their own fully isolated Livro agent,
paid for via prepaid USDC credits. See `WRITEUP.md`'s "Multi-tenant
expansion" section for the full architecture and reasoning; this is the
condensed how-to.

### 8.1 Build ZeroClaw with Cloud API support

The prebuilt binary and the `whatsapp-web`-only source build used earlier
in this guide do **not** include WhatsApp Cloud API support --
`channel-whatsapp-cloud` is a separate compile-time feature, confirmed live
(`DEVIATIONS.md` Section 10). You need:

```sh
./install.sh --source --preset full --skip-quickstart
```

This resolves ZeroClaw's own "every feature" set at build time rather than
us hardcoding a feature list here. Requires Rust 1.96.1+ (`rustc --version`)
-- if `rustup update stable` fails repeatedly in your environment, see
`DEVIATIONS.md` Section 11 for a working manual-install fallback.

### 8.2 Meta WhatsApp Business setup

You do **not** need to wait for business verification to start development
-- Meta provisions a free test phone number immediately:

1. business.facebook.com → create a Meta Business Account.
2. developers.facebook.com → My Apps → Create App (Business type) → add the
   WhatsApp product. Note the test phone number's **phone number ID**.
3. Add up to 5 test recipient numbers (your own), verified via SMS code.
4. Note the **temporary access token** (App dashboard), the **app secret**
   (App Settings → Basic), and pick your own **verify token** (any string).
5. Don't set the webhook Callback URL yet -- that needs the gate's real
   public URL, which doesn't exist until Section 8.4.
6. Separately, start Meta's **Business Verification** whenever you're ready
   for a real production number -- this is the slow part (days), so start
   it in parallel rather than waiting to begin.

### 8.3 Environment variables the gate needs

Set these wherever you deploy (Railway env vars, never in a committed file):

```
LIVRO_PLATFORM_DIR=/data/platform
LIVRO_INSTALL_ROOT=/data/zeroclaw
LIVRO_CONFIG_TEMPLATES_DIR=/app/config
LIVRO_CONFIG_TOML_PATH=/data/zeroclaw/config.toml
LIVRO_OWNER_WALLET=7iwbvhRDZjCM8hEvw5zJMUdrziekew1fZfS3WEGSL8Gr
LIVRO_USDC_MINT=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v  # mainnet; confirm current before relying on it
LIVRO_META_PHONE_NUMBER_ID=<from 8.2>
LIVRO_META_ACCESS_TOKEN=<from 8.2 -- secret>
LIVRO_META_APP_SECRET=<from 8.2 -- secret>
LIVRO_GATE_VERIFY_TOKEN=<the string you picked in 8.2>
```

### 8.4 Deploy

Build and run `Dockerfile` / `entrypoint.sh` (co-located ZeroClaw +
gate, ZeroClaw bound to loopback only, gate on the public port -- see
`WRITEUP.md` for why). On Railway: one service, one persistent volume
mounted where `LIVRO_PLATFORM_DIR`/`LIVRO_INSTALL_ROOT` point, a generated
public domain for the gate's port only. Confirm from outside Railway that
only the gate's domain responds -- ZeroClaw's port must not be reachable.

Once deployed, go back to Meta's dashboard and set the webhook Callback URL
to `https://<your-railway-domain>/webhook`, subscribe to the `messages`
field, and verify using the token from 8.2/8.3.

### 8.5 First live multi-tenant test

Message the WhatsApp test number from a number that has never messaged it
before. You should get a "setting up your account" reply, then a "you're
all set, $1.00 trial credit" message within a few seconds (the
provisioning + `/admin/reload` cycle). Confirm a second, different test
number gets a genuinely separate workspace (no shared ledger data), and
that exhausting the trial credit produces a top-up link instead of a
response, with zero Anthropic spend for that blocked message (check
`costs.jsonl` has no new entry).
