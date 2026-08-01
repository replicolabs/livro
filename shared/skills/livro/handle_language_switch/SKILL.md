---
name: handle_language_switch
description: Detect and apply an explicit request to switch Livro's reply language between pt-BR and English -- never inferred, only on direct request
version: 0.1.0
author: livro
tags: [livro, language, localization]
---

# Handle language switch

Applies `docs/language.md` (the localization addendum). Livro replies in
**Brazilian Portuguese (pt-BR) by default for every new user, with no
onboarding question** (Section 1.1). English is available only on an
explicit, direct request (Section 1.2) -- never inferred from a stray
English word, a pasted English client name, a device locale, or anything
short of the freelancer plainly asking to switch.

## What to do

1. **Do not run a language check on every message.** This is a dedicated
   step for messages that plausibly concern language itself (the
   freelancer's phrasing reads like a request about which language you
   should use), not a background scan of ordinary conversation.

2. When a message plausibly concerns language, check it deterministically
   via `shell`:
   `echo '{"message": "<the message>"}' | python3 -m rendering detect_language_switch`
   This never guesses from vocabulary mix or content -- it matches only a
   curated set of direct trigger phrases in both directions (see
   `rendering/rendering/language_switch.py`).

3. Act on the result:
   - **`switch_to_en`** or **`switch_to_pt`** -- update
     `workspace/config/user_preferences.json`'s `language` field
     immediately (`pt-BR` or `en`), then render and send the confirmation
     **in the new language** via `shell`:
     `echo '{"new_language": "en"}' | python3 -m rendering language_switch_confirmation`.
     The confirmation itself is the proof to the freelancer that the switch
     took effect.
   - **`ambiguous`** -- do not switch. Render and send a clarifying
     question in the **current** (not requested) language via
     `echo '{"current_language": "..."}' | python3 -m rendering language_switch_clarification`,
     then wait for an unambiguous answer before touching the preference.
   - **`no_signal`** -- this message isn't actually about language. Do
     nothing here; continue with whatever the message actually asked for.

4. **Every subsequent message to this freelancer, including scheduled ones**
   (`monthly_reminder`, `threshold_watch`, `backup_export` notifications)
   **must read the current `user_preferences.json` language and render
   through it** -- never hold a language choice only for the current reply.
   See the `rendering` skill note repeated across every other skill and SOP
   in this bundle: read `language` from `workspace/config/user_preferences.json`
   before rendering any outbound text, and pass it explicitly to every
   `python3 -m rendering <template>` call.
