"""Read-only extraction of routing info from a Meta WhatsApp Cloud API
webhook payload. Operates on a PARSED COPY only -- the raw bytes used for
forwarding (see forwarding.py) must never pass through this module.

Meta's webhook delivers more than just inbound user messages on the same
URL -- message status callbacks (sent/delivered/read receipts), template
status updates, etc. also arrive here. Only an actual inbound message
(`messages` present in the `value` object) needs tenant lookup/billing/
forwarding; anything else is out of scope for this first pass and is
reported as `None` so the caller can safely no-op (acknowledge with 200,
forward nowhere) rather than misroute a non-message event to some tenant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InboundMessage:
    wa_id: str
    message_id: str
    phone_number_id: str
    message_type: str


def extract_inbound_message(payload: dict) -> Optional[InboundMessage]:
    """Return the first inbound message found in a Meta webhook payload, or
    None if this payload isn't a user message (e.g. a status callback, or a
    shape this parser doesn't recognize -- fail closed to "no-op", never
    guess a tenant for an unrecognized shape).
    """
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages")
                if not messages:
                    continue  # status callback or other non-message event
                message = messages[0]
                contacts = value.get("contacts", [])
                wa_id = contacts[0]["wa_id"] if contacts else message.get("from")
                if not wa_id:
                    continue
                return InboundMessage(
                    wa_id=wa_id,
                    message_id=message.get("id", ""),
                    phone_number_id=value.get("metadata", {}).get("phone_number_id", ""),
                    message_type=message.get("type", "unknown"),
                )
    except (AttributeError, IndexError, KeyError, TypeError):
        return None
    return None
