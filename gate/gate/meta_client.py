"""Thin wrapper around Meta's WhatsApp Cloud API Send Message endpoint.

Used ONLY for the gate's own direct replies (welcome/provisioning,
insufficient-balance top-up prompts, top-up confirmations) -- never for
anything a tenant's own ZeroClaw agent would send, which goes through
ZeroClaw's normal outbound path after a forwarded, approved turn.
"""
from __future__ import annotations

import httpx

META_GRAPH_BASE_URL = "https://graph.facebook.com/v21.0"


async def send_text_message(
    client: httpx.AsyncClient,
    phone_number_id: str,
    access_token: str,
    to_wa_id: str,
    text: str,
    base_url: str = META_GRAPH_BASE_URL,
) -> httpx.Response:
    url = f"{base_url}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_wa_id,
        "type": "text",
        "text": {"body": text},
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    return await client.post(url, json=payload, headers=headers)
