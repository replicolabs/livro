# Livro

Livro is a bookkeeping and tax assistant that lives entirely inside WhatsApp, built for
Brazilian freelancers who get paid in USDC by clients outside Brazil. There is nothing to
install and no dashboard to learn. A freelancer sends a message, and Livro tracks income and
expenses, calculates the tax actually owed, generates invoices with Solana Pay links, confirms
payments against the official Central Bank exchange rate, and exports a report ready to hand
to an accountant. It never asks the freelancer to hand over a wallet's private key, and it
never signs or files anything on their behalf.

## Demo

[![Watch the Livro demo](https://img.youtube.com/vi/vtrgp5QWenA/maxresdefault.jpg)](https://youtu.be/vtrgp5QWenA)

Watch it here: https://youtu.be/vtrgp5QWenA

## Table of contents

- [The problem](#the-problem)
- [What Livro does](#what-livro-does)
- [Who it's for](#whos-its-for)
- [Custody model: what Livro never holds](#custody-model-what-livro-never-holds)
- [Security and the trust boundary](#security-and-the-trust-boundary)
- [How a single conversation flows](#how-a-single-conversation-flows)
- [Skills](#skills)
- [Standard Operating Procedures (SOPs)](#standard-operating-procedures-sops)
- [The ledger, and why every record is append only](#the-ledger-and-why-every-record-is-append-only)
- [Tax engine correctness](#tax-engine-correctness)
- [Architecture](#architecture)
- [Multi-tenant platform](#multi-tenant-platform)
- [Repository structure](#repository-structure)
- [Tech stack](#tech-stack)
- [Setup, local](#setup-local)
- [Setup, production (Railway)](#setup-production-railway)
- [Testing](#testing)
- [Known limitations and scope disclaimers](#known-limitations-and-scope-disclaimers)
- [Non-goals](#non-goals)
- [License](#license)

## The problem

A Brazilian freelancer working for foreign clients and getting paid in USDC sits between two
systems that were not built with each other in mind. Brazilian tax law expects ordinary income
tax on the amount received (Carnê-Leão) and separately expects capital gains tax whenever that
crypto is later converted or spent, calculated against a weighted average cost basis. Almost
nobody tracks both correctly by hand, and most freelancers in this position have no accountant
on retainer and are keeping a spreadsheet at best. Livro exists to close that gap without
asking the freelancer to learn a new tool, install anything, or trust a platform with their
funds.

## What Livro does

- Tracks income and expenses from a plain WhatsApp conversation, in Brazilian Portuguese by
  default, switching to English only on explicit request.
- Generates client invoices as Solana Pay links, with a fresh receiving address for every
  invoice, never reused.
- Polls the chain for payment, classifies what actually arrived (an exact match, an
  overpayment, an underpayment, the wrong asset, or a late payment) and books it correctly
  instead of assuming the best case.
- Looks up the official BACEN (Banco Central do Brasil) PTAX exchange rate for the day the
  payment was received, including a documented weekend and holiday fallback rule, and converts
  the payment to BRL.
- Never assumes what the freelancer wants to do with a payment next. It asks, or follows an
  explicit standing preference, and tracks whichever of three outcomes the freelancer chooses:
  convert to BRL, hold as USDC, or allocate into a tokenized Brazilian government bond.
- Computes two separate tax obligations Brazilian law actually imposes on this kind of income:
  ordinary income tax at the moment of receipt (Carnê-Leão), and capital gains tax at the
  moment of disposal, using a proper chronological cost-basis replay.
- Proactively reminds the freelancer before the monthly DARF deadline, and separately watches
  for approach toward the IN 1888 / DeCripto crypto self-reporting threshold.
- Lets the freelancer register income Livro cannot see directly (a payment that never touched
  the watched wallet), tagged distinctly from directly observed income so nothing is ever
  blended silently.
- Exports an accountant-ready report on request.
- Refuses to treat any instruction that did not come from the freelancer's own authenticated
  chat as their confirmed intent, even if it is phrased identically and even if it arrives
  disguised as coming from the client.

## Who it's for

A Brazilian freelancer operating as an individual (pessoa física, no company), receiving USDC
directly into a self-custody Solana wallet from clients based outside Brazil. Typically no
accountant on retainer, and currently tracking payments in a spreadsheet, if at all.

## Custody model: what Livro never holds

Livro never holds a private key capable of spending funds, at any point, for any user. Every
fund-adjacent action it can take, a refund, a bond allocation, produces an unsigned transaction
that the freelancer reviews and signs themselves with their own wallet. Nothing in Livro is a
compiled plugin with elevated capability; the entire build is instruction sets (skills and
SOPs) running on top of a stock agent runtime's built-in tools.

This is enforced in code, not just described in prose:

- Every ledger record type (a disposition instruction, a refund draft, a bond position) is
  validated at construction time. A record cannot be created with a missing or fabricated
  confirmation timestamp; the code raises an error immediately rather than allowing an invalid
  record to be written to disk.
- A deterministic guard, not an LLM judgment call, checks every piece of content that could
  plausibly carry a fund-moving instruction before it is ever reasoned about. Only the
  freelancer's own authenticated chat is ever treated as a trusted source for that kind of
  instruction, regardless of phrasing or language.

## Security and the trust boundary

The realistic threat here is not a technical exploit. It is a message that is not actually from
the freelancer, embedded in a transaction memo, relayed as "the client said," or arriving
through any channel other than the freelancer's own authenticated chat, that tries to get Livro
to redirect a payment, change a disposition, or otherwise treat unverified content as confirmed
freelancer intent.

Livro's defense routes every untrusted piece of content, including anything that arrives inside
a transaction memo, a relayed message, or a webhook payload, through a guard that checks the
source first. Only the freelancer's own authenticated chat is ever trusted to carry a
fund-moving instruction. The identical wording from any other source is refused and logged,
never silently ignored.

This is proven by an automated test, not only a manual demo: a redirect instruction embedded
in a transaction memo, a redirect instruction framed as coming from the client, and a redirect
instruction embedded in a webhook payload are all refused, while the exact same words typed
directly by the freelancer are allowed. See `trust/tests/test_guard.py`.

## How a single conversation flows

1. The freelancer tells Livro to invoice a client. Livro drafts the invoice text and a Solana
   Pay link pointing at a fresh, never-reused receiving address.
2. Livro watches the chain for that specific address. When a payment arrives, it fetches the
   BACEN PTAX rate for that date and classifies exactly what arrived against what was expected.
3. Livro asks the freelancer what to do with the payment, unless a standing preference already
   answers that question, and records the answer permanently.
4. If the answer requires it, Livro computes the correct tax consequence: an income entry at
   the moment of receipt, and later a disposal entry with a proper cost-basis gain or loss
   calculation if the funds are converted or spent.
5. Before a deadline, Livro proactively reminds the freelancer what they owe, and separately
   asks whether there is any income it would not otherwise know about.
6. On request, Livro exports everything in a shape ready to hand to an accountant.

## Skills

Livro's behavior is defined as a set of skill instructions rather than hardcoded logic, so each
one can be read, audited, and tested independently:

| Skill | Purpose |
|---|---|
| `draft_invoice` | Builds a client invoice with a fresh Solana Pay address |
| `classify_receipt` | Determines what actually arrived against what was expected, and routes untrusted content through the trust guard first |
| `book_receipt` | Fetches the BACEN PTAX rate and writes the income ledger entry |
| `draft_refund` | Prepares an unsigned refund transaction, never auto-filled, always from the freelancer's own typed and confirmed address |
| `draft_bond_allocation` | Prepares an unsigned allocation into a tokenized Brazilian government bond, only on explicit request |
| `register_external_holding` | Lets the freelancer declare income or holdings Livro cannot see directly |
| `annual_summary` | Produces a yearly overview of income, disposals, and tax owed |
| `export_for_contador` | Exports everything in a shape ready for an accountant |
| `handle_language_switch` | Deterministically switches between Portuguese and English on explicit request only, never inferred |

## Standard Operating Procedures (SOPs)

SOPs are the cron-triggered automations that run without the freelancer needing to ask:

| SOP | Trigger | Purpose |
|---|---|---|
| `watch_payment` | Every 5 minutes | Polls every open invoice, classifies and books any new receipt, and captures the freelancer's disposition instruction |
| `monthly_reminder` | Daily | Proactively reminds the freelancer of their Carnê-Leão liability before the DARF deadline, and asks about income Livro cannot see |
| `threshold_watch` | Every 6 hours | Flags approach toward the IN 1888 / DeCripto monthly self-report threshold before it is crossed |
| `backup_export` | Weekly | Exports the ledger to a destination the freelancer controls, so a lost or broken device does not cost years of tax records |

## The ledger, and why every record is append only

Every financial record Livro produces (an income entry, a disposal entry, a disposition
instruction, an external holding) is written once and never edited or overwritten. A correction
is a new record, never a mutation of an old one. This is the same discipline a real accountant
would insist on: the history has to be reconstructable, and a past record has to mean what it
meant when it was written. Every record type is structurally validated at the moment it is
constructed, so a malformed or incomplete record cannot reach disk at all.

## Tax engine correctness

Rather than trust a single AI-researched tax table, this project fetched Receita Federal's own
published worked examples for the current sliding-reduction income tax law and reproduced all
of them exactly, now committed as permanent regression tests. Several figures in the tax tables
are explicitly marked as verified against a primary source; a small number of genuinely
uncertain figures (the exact IN 1888 / DeCripto threshold, and one narrow capital-gains
exemption carve-out) are explicitly flagged as unverified with a caveat explaining what is
uncertain and why, rather than presented with false confidence.

## Architecture

At the center of Livro is an agent runtime that hosts the actual conversation and tool use.
Everything the freelancer-facing behavior does (drafting invoices, watching payments,
calculating tax, exporting reports) is expressed as skill and SOP instructions running on top
of that runtime's built-in tools: reading and writing files, making HTTP requests, asking the
user a question, and escalating to a human when something is genuinely ambiguous. No part of
the freelancer-facing logic is a compiled plugin with elevated capability.

Four independent, pure code packages sit underneath the skills and SOPs and do the actual
computation:

- `tax_engine`, Carnê-Leão brackets, weighted-average cost basis, capital gains, the IN 1888
  threshold watch, and the BACEN PTAX weekend and holiday fallback rule.
- `rendering`, bilingual message formatting, locale-correct number and date formatting, and
  deterministic language-switch detection.
- `trust`, the fund-moving-instruction guard described above.
- `ledger`, the structural validation dataclasses for every ledger record type.

## Multi-tenant platform

The core product described above was built first for a single freelancer, run from one paired
WhatsApp account. It was then extended so that any freelancer can message a single shared
WhatsApp Business number and get their own fully isolated Livro agent, hosted continuously
rather than run by hand, paying for usage in prepaid USDC credits rather than needing to supply
their own API key.

Two real constraints shaped this design:

1. A WhatsApp Business number has exactly one webhook callback URL. It cannot fan out
   automatically to a different destination per sender. A small routing and billing service,
   referred to internally as the gate, sits in front of the agent runtime: the one webhook URL
   points at the gate, which resolves the sender to a tenant and forwards the message to that
   tenant's own isolated agent.
2. Workspace-level sandboxing enforces a boundary around one whole workspace directory, with no
   concept of a sub-tenant boundary inside it. A shared workspace partitioned by folder would
   give no real enforced isolation between different freelancers' financial ledgers, which is
   unacceptable given the entire premise of this product is tax-record integrity. Each tenant
   therefore gets a genuinely separate agent instance: its own workspace, its own risk profile,
   its own channel binding.

Because the gate already has to intercept every message to do the routing a shared webhook
cannot do on its own, it is also the natural place to enforce a credit balance check before any
message reaches the agent at all. A tenant without enough balance never reaches the model, so
no cost is ever incurred on their behalf.

The gate also acknowledges the WhatsApp platform's webhook immediately and processes the actual
agent turn in the background, since a real conversation, including tool calls and multi-step
reasoning, routinely takes longer than a webhook is expected to stay open. The reply still
reaches the user through the agent runtime's own outbound message API, independent of the
webhook response.

New tenants are provisioned automatically on first contact: a workspace is created, a config
entry is appended without disturbing any existing tenant's configuration, and a small free
trial credit is granted so a new user can see Livro work before needing to pay. Offboarding
disables a tenant's configuration rather than deleting it, consistent with the append-only
discipline used everywhere else in this project.

## Repository structure

```
gate/              Multi-tenant routing and billing service (webhook, provisioning,
                    forwarding, balance tracking)
platform_ledger/   Tenant and billing record dataclasses
ledger/            Per-tenant financial record dataclasses
tax_engine/        Carne-Leao, cost basis, capital gains, PTAX lookup and fallback
rendering/         Bilingual (pt-BR/English) message formatting
trust/             The fund-moving-instruction guard
sops/              The four cron-triggered SOPs
shared/skills/     The skill bundle every tenant's agent loads
config/            Example configuration templates
integration_tests/ End-to-end simulated-chain tests wiring tax_engine and ledger together
transcripts/       Captured live-run transcripts
Dockerfile         Build for the co-located agent runtime and gate deployment
entrypoint.sh      Container boot sequence and one-time configuration seeding
```

## Tech stack

- Python (FastAPI, httpx, tomlkit) for the gate service and every pure computation package.
- An agent runtime written in Rust, hosting the actual conversation, tool use, and skill and
  SOP execution.
- Claude Sonnet 5 as the underlying model.
- Solana, for Solana Pay invoicing and payment confirmation, and USDC as the settlement asset.
- Meta's WhatsApp Cloud API as the messaging channel.
- Docker and Railway for deployment.

## Setup, local

Each pure code package is independently installable and testable:

```sh
cd tax_engine
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

Repeat the same three commands inside `rendering/`, `trust/`, `ledger/`, `platform_ledger/`,
and `gate/`. Before relying on any tax figure for a real filing, read the `verified` and
`verification_caveat` fields in every file under `tax_engine/tax_tables/`.

For a single-freelancer local run, install the agent runtime binary, copy `sops/` and
`shared/skills/livro/` into the install, copy the files in `config/` ending in `.example` and
fill in real values, then pair a WhatsApp account. Full step-by-step instructions are in
`SETUP.md`.

## Setup, production (Railway)

The production deployment runs the agent runtime and the gate as two processes inside one
container, with the agent runtime bound to loopback only so it is not reachable from outside
the container under any circumstance. Only the gate's port is exposed publicly.

At minimum, the following need to be set as environment variables on the service before
deploying:

- Meta WhatsApp Business credentials (phone number ID, access token, app secret, and a verify
  token you choose yourself).
- The model provider's API key, set using the runtime's own environment-variable naming
  convention rather than assumed from documentation, since that convention has changed across
  versions.
- A Solana wallet address the operator controls, used to receive prepaid USDC credit top-ups.
- The USDC token mint address for the network in use.
- Paths for the install root, the config file, the config templates directory, and the
  platform tenant registry.

A persistent volume must be attached to the service and mounted where the config file and
tenant workspaces live. Without it, every restart or redeploy discards all tenant data, which
defeats the entire point of a hosted, always-on service.

## Testing

Every pure code package ships with its own automated test suite and no part of this project's
correctness claims rest on manual testing alone. As of this writing:

- `tax_engine`, reproduces Receita Federal's own published worked examples exactly, in addition
  to unit coverage of every bracket and fallback rule.
- `rendering`, covers locale-correct formatting and deterministic language-switch detection.
- `trust`, reproduces the exact prompt-injection scenario this project's threat model is built
  around, as an automated test rather than only a manual demo moment.
- `ledger` and `platform_ledger`, cover every validation rule that keeps an invalid record from
  ever being constructed.
- `gate`, covers tenant resolution, provisioning, balance derivation, cost reconciliation, and
  byte-identical webhook forwarding, since any re-serialization there would silently break
  Meta's signature verification for every tenant.
- `integration_tests`, a continuous simulated chain from invoice through payment through
  disposal, wiring `tax_engine` and `ledger` together rather than exercising either in
  isolation.

## Known limitations and scope disclaimers

Livro's ledger is only ever as complete as what passes through the wallet it actually watches.
Any output touching a tax figure or cost basis carries a disclaimer to this effect, and the
freelancer has an explicit path to declare income Livro cannot see directly, tagged distinctly
from directly observed income so the two are never blended silently.

A small number of figures in the tax tables are explicitly flagged as unverified, with a
caveat explaining exactly what is uncertain. Anyone relying on Livro for a real filing should
get an accountant to confirm those specific points first.

## Non-goals

Livro does not file anything with Receita Federal directly. It does not handle invoice
mechanics for MEI-registered businesses. It does not hold custody credentials for the bond
allocation partner. It has no signing capability of any kind, for any user, under any
circumstance. It does not automate a client's crypto onboarding. It does not automatically
resolve an ambiguous payment exception; it surfaces the ambiguity and lets the freelancer
decide.

## License

See the repository for license details.
