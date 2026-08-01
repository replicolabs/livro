"""The single highest-risk correctness point in the whole gate design
(per the approved plan's Verification section): prove forwarding is
byte-identical and that a signature computed on the ORIGINAL body still
validates against the FORWARDED body, exactly as ZeroClaw's own
verify_whatsapp_signature would check it.
"""
import httpx
import pytest

from gate.forwarding import forward_to_zeroclaw, select_forward_headers
from tests.mock_zeroclaw import (
    APP_SECRET,
    ReceivedCall,
    compute_meta_signature,
    make_mock_zeroclaw_app,
)

RAW_META_PAYLOAD = (
    b'{"object":"whatsapp_business_account","entry":[{"id":"1","changes":'
    b'[{"value":{"messaging_product":"whatsapp","metadata":{"phone_number_id":"pn1"},'
    b'"contacts":[{"wa_id":"5511999999999"}],'
    b'"messages":[{"from":"5511999999999","id":"wamid.1","type":"text",'
    b'"text":{"body":"invoice a client for 10 USDC"}}]},"field":"messages"}]}]}'
)


@pytest.mark.asyncio
async def test_forwarded_body_is_byte_identical():
    received: list[ReceivedCall] = []
    mock_app = make_mock_zeroclaw_app(received)
    transport = httpx.ASGITransport(app=mock_app)

    signature = compute_meta_signature(APP_SECRET, RAW_META_PAYLOAD)
    headers = {"content-type": "application/json", "x-hub-signature-256": signature}

    async with httpx.AsyncClient(transport=transport, base_url="http://zeroclaw.internal") as client:
        response = await forward_to_zeroclaw(
            "t_abc123", RAW_META_PAYLOAD, headers, client, base_url="http://zeroclaw.internal"
        )

    assert response.status_code == 200  # mock only returns 200 if signature validated
    assert len(received) == 1
    assert received[0].body == RAW_META_PAYLOAD  # byte-for-byte
    assert received[0].alias == "t_abc123"
    assert received[0].signature_valid is True


@pytest.mark.asyncio
async def test_signature_survives_forwarding_even_with_extra_incoming_headers():
    """Real Meta requests carry extra headers (User-Agent, Host, etc.) the
    gate must NOT forward blindly -- select_forward_headers strips them,
    and the signature must still validate on the receiving end.
    """
    received: list[ReceivedCall] = []
    mock_app = make_mock_zeroclaw_app(received)
    transport = httpx.ASGITransport(app=mock_app)

    signature = compute_meta_signature(APP_SECRET, RAW_META_PAYLOAD)
    incoming_headers = {
        "content-type": "application/json",
        "x-hub-signature-256": signature,
        "user-agent": "facebookexternalhit/1.1",
        "host": "example.railway.app",
        "content-length": str(len(RAW_META_PAYLOAD)),
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://zeroclaw.internal") as client:
        response = await forward_to_zeroclaw(
            "t_abc123", RAW_META_PAYLOAD, incoming_headers, client, base_url="http://zeroclaw.internal"
        )

    assert response.status_code == 200
    assert received[0].signature_valid is True


def test_select_forward_headers_strips_everything_except_the_allowlist():
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": "sha256=abc",
        "Host": "example.com",
        "User-Agent": "facebookexternalhit/1.1",
        "Content-Length": "123",
    }
    forwarded = select_forward_headers(headers)
    assert forwarded == {"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=abc"}


@pytest.mark.asyncio
async def test_tampered_body_fails_signature_as_expected():
    """Sanity check on the mock itself: a body that doesn't match the
    signature must be rejected, proving the mock is actually exercising
    the same check ZeroClaw performs, not just returning 200 unconditionally.
    """
    received: list[ReceivedCall] = []
    mock_app = make_mock_zeroclaw_app(received)
    transport = httpx.ASGITransport(app=mock_app)

    wrong_signature = compute_meta_signature(APP_SECRET, b"different body entirely")
    headers = {"content-type": "application/json", "x-hub-signature-256": wrong_signature}

    async with httpx.AsyncClient(transport=transport, base_url="http://zeroclaw.internal") as client:
        response = await forward_to_zeroclaw(
            "t_abc123", RAW_META_PAYLOAD, headers, client, base_url="http://zeroclaw.internal"
        )

    assert response.status_code == 401
    assert received[0].signature_valid is False
