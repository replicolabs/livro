"""FastAPI app: Meta's one WhatsApp Cloud API webhook Callback URL.

The HTTP request-handling flow lives here behind a small dependency-
injection seam (`GateDependencies`), so it can be tested against fakes
(tests/test_app.py) independently of the real tenant-lookup/balance/
provisioning/messaging wiring, which lives in wiring.py and is only
assembled for the real, environment-configured production app built at
the bottom of this module. `GateDependencies`' own defaults are the safe
fallback: every sender is "unknown" and nothing is ever forwarded to
ZeroClaw without an explicit resolver deciding to.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import logging

import httpx
from fastapi import BackgroundTasks, FastAPI, Request, Response

from gate.forwarding import forward_to_zeroclaw
from gate.parsing import InboundMessage, extract_inbound_message

VERIFY_TOKEN = os.environ.get("LIVRO_GATE_VERIFY_TOKEN", "")

# Without this, INFO/WARNING calls below are silently dropped -- nothing
# else in the process configures logging, so Python's logging module falls
# back to only printing WARNING+ via its no-op "handler of last resort",
# and even that never reaches Railway's captured stdout the way print() or
# uvicorn's own configured loggers do.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gate")


# ── Dependency seam ──────────────────────────────────────────────────────
# TenantResolver: wa_id -> tenant_alias, or None if unknown (triggers
# provisioning once gate/provisioning.py exists). BalanceChecker: tenant_alias
# -> True if the turn may proceed. Both are async so real implementations
# can do file I/O without blocking the event loop.

TenantResolver = Callable[[str], Awaitable[Optional[str]]]
BalanceChecker = Callable[[str], Awaitable[bool]]
UnknownSenderHandler = Callable[[InboundMessage, bytes, dict], Awaitable[None]]
InsufficientBalanceHandler = Callable[[str, InboundMessage], Awaitable[None]]


async def _default_resolver(wa_id: str) -> Optional[str]:
    return None  # every sender is "unknown" until provisioning.py is wired in


async def _default_balance_check(tenant_alias: str) -> bool:
    return False  # fail closed: never forward without an explicit balance pass


async def _default_unknown_sender(msg: InboundMessage, raw_body: bytes, headers: dict) -> None:
    return None  # no-op until provisioning.py is wired in


async def _default_insufficient_balance(tenant_alias: str, msg: InboundMessage) -> None:
    return None  # no-op until balance.py's top-up reply is wired in


@dataclass
class GateDependencies:
    resolve_tenant: TenantResolver = _default_resolver
    check_balance: BalanceChecker = _default_balance_check
    on_unknown_sender: UnknownSenderHandler = _default_unknown_sender
    on_insufficient_balance: InsufficientBalanceHandler = _default_insufficient_balance
    zeroclaw_base_url: str = "http://127.0.0.1:42617"
    http_client: httpx.AsyncClient = field(default_factory=httpx.AsyncClient)


def create_app(deps: Optional[GateDependencies] = None) -> FastAPI:
    deps = deps or GateDependencies()
    app = FastAPI()

    @app.get("/webhook")
    async def verify(request: Request) -> Response:
        params = request.query_params
        if (
            params.get("hub.mode") == "subscribe"
            and params.get("hub.verify_token") == VERIFY_TOKEN
            and VERIFY_TOKEN
        ):
            return Response(content=params.get("hub.challenge", ""), media_type="text/plain")
        return Response(status_code=403)

    async def _forward_and_log(tenant_alias: str, raw_body: bytes, headers: dict) -> None:
        # Runs after the response to Meta has already been sent (FastAPI
        # BackgroundTasks). ZeroClaw's own handler awaits the full agent
        # turn -- tool calls, LLM iterations, sending the reply -- before
        # it responds (confirmed against source), which routinely exceeds
        # any timeout Meta would tolerate on the webhook itself. Meta only
        # needs a fast ack; the actual reply reaches the user via
        # ZeroClaw's own outbound WhatsApp Send API call, independent of
        # this response entirely.
        try:
            upstream = await forward_to_zeroclaw(
                tenant_alias, raw_body, headers, deps.http_client, deps.zeroclaw_base_url
            )
            if upstream.status_code != 200:
                logger.warning(
                    "zeroclaw forward for %s returned %s: %r",
                    tenant_alias, upstream.status_code, upstream.text[:500],
                )
        except Exception:
            logger.exception("zeroclaw forward for %s failed", tenant_alias)

    @app.post("/webhook")
    async def receive(request: Request, background_tasks: BackgroundTasks) -> Response:
        raw_body = await request.body()
        headers = dict(request.headers)

        try:
            parsed = await request.json()
        except ValueError:
            # Not JSON at all -- can't be a real Meta payload. Ack anyway
            # (200) so Meta doesn't retry something that will never parse.
            logger.warning("webhook body was not valid JSON: %r", raw_body[:500])
            return Response(status_code=200)

        message = extract_inbound_message(parsed)
        if message is None:
            # Status callback or unrecognized shape -- no-op, ack it. Logged
            # at INFO (not silent) since this is indistinguishable from a
            # real inbound message this parser failed to recognize --
            # confirmed live that this ambiguity cost real debugging time.
            logger.info("webhook payload produced no InboundMessage: %s", parsed)
            return Response(status_code=200)

        tenant_alias = await deps.resolve_tenant(message.wa_id)
        if tenant_alias is None:
            await deps.on_unknown_sender(message, raw_body, headers)
            return Response(status_code=200)

        if not await deps.check_balance(tenant_alias):
            await deps.on_insufficient_balance(tenant_alias, message)
            return Response(status_code=200)

        background_tasks.add_task(_forward_and_log, tenant_alias, raw_body, headers)
        return Response(status_code=200)

    return app


def _build_default_app() -> FastAPI:
    """Module-level `app` for `uvicorn gate.app:app` in production. Uses
    the real wiring (gate/wiring.py) when the required env vars are
    present; falls back to the safe (nothing-ever-forwards) defaults
    otherwise, so `import gate.app` stays safe in tests and doesn't
    require a full production environment just to load the module.
    """
    try:
        from gate.wiring import build_production_dependencies

        return create_app(build_production_dependencies())
    except KeyError:
        return create_app()


app = _build_default_app()
