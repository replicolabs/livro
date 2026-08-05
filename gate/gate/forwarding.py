"""Raw-bytes-preserving forward to ZeroClaw's internal per-tenant webhook.

Meta's HMAC-SHA256 signature (X-Hub-Signature-256) is computed over the
EXACT raw request body bytes and verified downstream inside ZeroClaw
(crates/zeroclaw-gateway/src/lib.rs::verify_whatsapp_signature, confirmed
directly against source). This module exists to hold that invariant in one
place: forward the byte-identical body and the signature header untouched.
Any re-serialization here (even producing semantically identical JSON)
silently breaks Meta's HMAC check on the receiving end -- there is no
Python-level error, ZeroClaw just returns 401 and Meta sees a failed
delivery.

Callers must extract routing information (sender id, message type) from a
SEPARATE parsed copy of the body (see parsing.py) -- never from anything
that touches or reconstructs the bytes passed to `forward_to_zeroclaw`.
"""
from __future__ import annotations

import httpx

ZEROCLAW_BASE_URL = "http://127.0.0.1:42617"

# Only headers ZeroClaw's webhook handler actually needs are forwarded.
# Content-Length is deliberately excluded -- httpx recomputes it correctly
# from the `content=` bytes we pass; forwarding a stale one risks a mismatch
# if any intermediate layer touches the body.
FORWARD_HEADER_NAMES = {"content-type", "x-hub-signature-256"}


def select_forward_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() in FORWARD_HEADER_NAMES}


# ZeroClaw's own /whatsapp/{alias} handler (confirmed against source,
# zeroclaw-gateway/src/lib.rs::handle_whatsapp_message_impl) awaits the
# ENTIRE agent turn -- tool calls, LLM iterations, and sending the reply
# via WhatsApp's Send API -- inline, before returning its own HTTP
# response. httpx's default timeout (5s total) is nowhere near enough for
# a real turn; confirmed live it caused this call to raise on anything
# past a trivial greeting, which the caller must never await inline
# before acking Meta (see app.py's use of BackgroundTasks). A real turn
# can still legitimately run past this if it invokes several tools in
# sequence, so this is generous, not tight -- bounded only to avoid a
# truly wedged connection lingering forever.
FORWARD_TIMEOUT_SECS = 300.0


async def forward_to_zeroclaw(
    tenant_alias: str,
    raw_body: bytes,
    headers: dict[str, str],
    client: httpx.AsyncClient,
    base_url: str = ZEROCLAW_BASE_URL,
) -> httpx.Response:
    """POST the untouched raw_body to ZeroClaw's internal alias route.

    `content=raw_body` (bytes, not `json=...`) is what guarantees httpx
    sends these exact bytes on the wire with no re-encoding.
    """
    url = f"{base_url}/whatsapp/{tenant_alias}"
    return await client.post(
        url,
        content=raw_body,
        headers=select_forward_headers(headers),
        timeout=FORWARD_TIMEOUT_SECS,
    )
