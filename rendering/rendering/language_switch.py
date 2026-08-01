"""Deterministic language-switch intent matcher. docs/language.md Section 3.

This matches only a curated set of clear, direct switch-request phrases (in
either direction) -- never a generic "does this text look English/Portuguese"
heuristic. That's the mechanism that keeps docs/language.md Section 1.2's
rule honest: a stray English word, an English client name, or a device
locale must never flip the preference. A message that isn't a recognized
trigger phrase, in either direction, is `no_signal` -- ordinary conversation,
not a candidate for switching at all.

A message that clearly mentions "language" without a clear direction is
`ambiguous` -- per Section 3, this should prompt a clarifying question in
the CURRENT language rather than silently doing nothing (no_signal) or
silently switching.
"""
from __future__ import annotations

import unicodedata

TRIGGERS_TO_EN = (
    "switch to english",
    "can you speak english",
    "can we speak english",
    "can we talk in english",
    "reply in english",
    "respond in english",
    "talk to me in english",
    "fala ingles",
    "fala em ingles",
    "muda para ingles",
    "mude para ingles",
    "responde em ingles",
    "responda em ingles",
    "responder em ingles",
    "quero em ingles",
    "pode falar em ingles",
)

TRIGGERS_TO_PT = (
    "switch back to portuguese",
    "switch to portuguese",
    "speak portuguese again",
    "speak portuguese",
    "reply in portuguese",
    "respond in portuguese",
    "volta pro portugues",
    "volta para o portugues",
    "volta ao portugues",
    "fala portugues",
    "fala em portugues",
    "responde em portugues",
    "responder em portugues",
    "muda para portugues",
    "mude para portugues",
)

LANGUAGE_MENTION_HINTS = (
    "language",
    "idioma",
    "lingua",
)

RESULT_SWITCH_TO_EN = "switch_to_en"
RESULT_SWITCH_TO_PT = "switch_to_pt"
RESULT_AMBIGUOUS = "ambiguous"
RESULT_NO_SIGNAL = "no_signal"


def _normalize(text: str) -> str:
    """Lowercase and strip accents so 'inglês'/'ingles', 'português'/
    'portugues' match the same trigger regardless of how the user typed it.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def detect_language_switch(message: str) -> str:
    """Classify a message as a language-switch request, or not.

    Returns one of RESULT_SWITCH_TO_EN, RESULT_SWITCH_TO_PT,
    RESULT_AMBIGUOUS, or RESULT_NO_SIGNAL. Callers (a skill's step
    instructions) should only ever act on the two directional results;
    RESULT_AMBIGUOUS means "ask, don't switch", and RESULT_NO_SIGNAL means
    "this message isn't about language at all -- don't even ask."
    """
    normalized = _normalize(message)

    matched_en = any(trigger in normalized for trigger in TRIGGERS_TO_EN)
    matched_pt = any(trigger in normalized for trigger in TRIGGERS_TO_PT)

    if matched_en and matched_pt:
        return RESULT_AMBIGUOUS
    if matched_en:
        return RESULT_SWITCH_TO_EN
    if matched_pt:
        return RESULT_SWITCH_TO_PT

    if any(hint in normalized for hint in LANGUAGE_MENTION_HINTS):
        return RESULT_AMBIGUOUS

    return RESULT_NO_SIGNAL
