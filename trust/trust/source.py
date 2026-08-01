"""Which content sources are trusted to carry a fund-moving instruction.

CLAUDE.md Section 1.4: only the freelancer's own authenticated chat is
trusted. Everything else -- a transaction memo, a client's message content
relayed through a payment or invoice flow, a webhook payload, forwarded or
quoted text -- is untrusted, no matter how plausible it reads.
"""
from __future__ import annotations

TRUSTED_SOURCE = "freelancer_authenticated_chat"

UNTRUSTED_SOURCES = frozenset({
    "transaction_memo",
    "onchain_message",
    "client_message_content",
    "webhook_payload",
    "forwarded_content",
    "quoted_text",
    "invoice_notes_field",
})

KNOWN_SOURCES = frozenset({TRUSTED_SOURCE}) | UNTRUSTED_SOURCES


def is_trusted_source(source: str) -> bool:
    """True only for the freelancer's own authenticated chat channel.

    Fails closed on an unrecognized source string: anything not explicitly
    TRUSTED_SOURCE is treated as untrusted, including a typo'd or unknown
    source name -- a new content channel added later must be explicitly
    added to TRUSTED_SOURCE (never) or UNTRUSTED_SOURCES to be recognized;
    until then it defaults to untrusted rather than silently trusted.
    """
    return source == TRUSTED_SOURCE
