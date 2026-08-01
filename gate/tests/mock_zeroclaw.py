"""A minimal stand-in for ZeroClaw's WhatsApp Cloud webhook handler,
replicating its actual signature-verification behavior (HMAC-SHA256 over
the raw body, `sha256=<hex>` header format) so tests can prove the gate's
forwarding preserves what ZeroClaw would actually check -- without needing
a real ZeroClaw process running.
"""
from __future__ import annotations

import hashlib
import hmac

from fastapi import FastAPI, Request, Response

APP_SECRET = "test-app-secret-shared-by-every-tenant"


def compute_meta_signature(app_secret: str, body: bytes) -> str:
    mac = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_meta_signature(app_secret: str, body: bytes, signature_header: str) -> bool:
    expected = compute_meta_signature(app_secret, body)
    return hmac.compare_digest(expected, signature_header)


class ReceivedCall:
    def __init__(self, alias: str, body: bytes, signature_valid: bool):
        self.alias = alias
        self.body = body
        self.signature_valid = signature_valid


def make_mock_zeroclaw_app(received_calls: list[ReceivedCall]) -> FastAPI:
    """received_calls is mutated in place so the test can inspect what
    actually arrived after making requests through the gate.
    """
    app = FastAPI()

    @app.post("/whatsapp/{alias}")
    async def receive(alias: str, request: Request) -> Response:
        raw_body = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        valid = verify_meta_signature(APP_SECRET, raw_body, signature)
        received_calls.append(ReceivedCall(alias, raw_body, valid))
        return Response(status_code=200 if valid else 401)

    return app
