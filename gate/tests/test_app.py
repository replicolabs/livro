"""End-to-end test of the gate's webhook endpoint: simulates what Meta
actually sends, through the full FastAPI app (tenant resolution -> balance
check -> forward-or-shortcircuit), landing on a mock ZeroClaw backend that
independently verifies the signature -- proving the whole chain, not just
forwarding.py in isolation.
"""
import json

import httpx
import pytest

from gate.app import GateDependencies, create_app
from gate.parsing import InboundMessage
from tests.mock_zeroclaw import APP_SECRET, ReceivedCall, compute_meta_signature, make_mock_zeroclaw_app

RAW_PAYLOAD = json.dumps({
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "1",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "pn1"},
                "contacts": [{"wa_id": "5511999999999"}],
                "messages": [{"from": "5511999999999", "id": "wamid.1", "type": "text",
                              "text": {"body": "hi"}}],
            },
            "field": "messages",
        }],
    }],
}).encode("utf-8")

STATUS_PAYLOAD = json.dumps({
    "entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "pn1"},
                                       "statuses": [{"id": "wamid.1", "status": "read"}]}}]}]
}).encode("utf-8")


def _headers_for(body: bytes) -> dict:
    return {
        "content-type": "application/json",
        "x-hub-signature-256": compute_meta_signature(APP_SECRET, body),
    }


async def _make_deps(resolve_result, balance_result):
    received: list[ReceivedCall] = []
    mock_app = make_mock_zeroclaw_app(received)
    zeroclaw_client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app), base_url="http://zeroclaw.internal"
    )

    unknown_calls = []
    insufficient_calls = []

    async def resolve_tenant(wa_id: str):
        return resolve_result

    async def check_balance(tenant_alias: str):
        return balance_result

    async def on_unknown_sender(msg: InboundMessage, raw_body: bytes, headers: dict):
        unknown_calls.append(msg)

    async def on_insufficient_balance(tenant_alias: str, msg: InboundMessage):
        insufficient_calls.append((tenant_alias, msg))

    deps = GateDependencies(
        resolve_tenant=resolve_tenant,
        check_balance=check_balance,
        on_unknown_sender=on_unknown_sender,
        on_insufficient_balance=on_insufficient_balance,
        zeroclaw_base_url="http://zeroclaw.internal",
        http_client=zeroclaw_client,
    )
    return deps, received, unknown_calls, insufficient_calls


@pytest.mark.asyncio
async def test_known_funded_tenant_gets_forwarded_byte_identical():
    deps, received, unknown_calls, insufficient_calls = await _make_deps("t_abc123", True)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.post("/webhook", content=RAW_PAYLOAD, headers=_headers_for(RAW_PAYLOAD))

    assert response.status_code == 200
    assert len(received) == 1
    assert received[0].alias == "t_abc123"
    assert received[0].body == RAW_PAYLOAD
    assert received[0].signature_valid is True
    assert unknown_calls == []
    assert insufficient_calls == []


@pytest.mark.asyncio
async def test_unknown_sender_never_reaches_zeroclaw():
    deps, received, unknown_calls, insufficient_calls = await _make_deps(None, True)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.post("/webhook", content=RAW_PAYLOAD, headers=_headers_for(RAW_PAYLOAD))

    assert response.status_code == 200
    assert received == []  # never forwarded -- no LLM spend possible
    assert len(unknown_calls) == 1
    assert unknown_calls[0].wa_id == "5511999999999"


@pytest.mark.asyncio
async def test_insufficient_balance_never_reaches_zeroclaw():
    """The core billing invariant: a message from a known-but-unfunded
    tenant must never be forwarded, since forwarding is the point of spend.
    """
    deps, received, unknown_calls, insufficient_calls = await _make_deps("t_abc123", False)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.post("/webhook", content=RAW_PAYLOAD, headers=_headers_for(RAW_PAYLOAD))

    assert response.status_code == 200
    assert received == []
    assert len(insufficient_calls) == 1
    assert insufficient_calls[0][0] == "t_abc123"


@pytest.mark.asyncio
async def test_status_callback_is_acknowledged_and_ignored():
    deps, received, unknown_calls, insufficient_calls = await _make_deps("t_abc123", True)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.post(
            "/webhook", content=STATUS_PAYLOAD, headers=_headers_for(STATUS_PAYLOAD)
        )

    assert response.status_code == 200
    assert received == []
    assert unknown_calls == []
    assert insufficient_calls == []


@pytest.mark.asyncio
async def test_verify_challenge_echoes_hub_challenge_with_correct_token(monkeypatch):
    monkeypatch.setattr("gate.app.VERIFY_TOKEN", "my-verify-token")
    deps, _, _, _ = await _make_deps("t_abc123", True)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "my-verify-token", "hub.challenge": "12345"},
        )

    assert response.status_code == 200
    assert response.text == "12345"


@pytest.mark.asyncio
async def test_verify_challenge_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr("gate.app.VERIFY_TOKEN", "my-verify-token")
    deps, _, _, _ = await _make_deps("t_abc123", True)
    gate_app = create_app(deps)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=gate_app), base_url="http://gate.internal"
    ) as client:
        response = await client.get(
            "/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
        )

    assert response.status_code == 403
