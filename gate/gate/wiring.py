"""Assembles the real GateDependencies from environment/config -- the
production wiring that plugs tenant_lookup, balance, meta_client, and
messages into app.py's dependency-injection seam. Kept separate from
app.py so the HTTP layer stays focused on request handling, and so tests
can exercise app.py against fakes without importing any of this.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

from gate.app import GateDependencies
from gate.balance import check_balance_gate
from gate.messages import account_disabled, insufficient_balance, welcome_provisioning, welcome_ready
from gate.meta_client import send_text_message
from gate.parsing import InboundMessage
from gate.provisioning import MetaCredentials
from gate.tenant_lookup import (
    TRIAL_CREDIT_USD,
    load_tenant_registry,
    provision_new_tenant,
    resolve_tenant_alias,
)
from gate.topup_watcher import create_pending_topup


def build_production_dependencies() -> GateDependencies:
    """Reads every value from the environment -- never a literal secret in
    source, same discipline as everywhere else in this project.
    """
    platform_dir = Path(os.environ["LIVRO_PLATFORM_DIR"])
    install_root = Path(os.environ["LIVRO_INSTALL_ROOT"])
    config_templates_dir = Path(os.environ["LIVRO_CONFIG_TEMPLATES_DIR"])
    config_toml_path = Path(os.environ["LIVRO_CONFIG_TOML_PATH"])
    owner_wallet = os.environ["LIVRO_OWNER_WALLET"]
    usdc_mint = os.environ["LIVRO_USDC_MINT"]

    meta = MetaCredentials(
        phone_number_id=os.environ["LIVRO_META_PHONE_NUMBER_ID"],
        access_token=os.environ["LIVRO_META_ACCESS_TOKEN"],
        verify_token=os.environ["LIVRO_GATE_VERIFY_TOKEN"],
        app_secret=os.environ["LIVRO_META_APP_SECRET"],
    )

    zeroclaw_client = httpx.AsyncClient()
    meta_client = httpx.AsyncClient()

    async def resolve_tenant(wa_id: str):
        return await resolve_tenant_alias(platform_dir, wa_id)

    async def check_balance(tenant_alias: str) -> bool:
        return check_balance_gate(platform_dir, tenant_alias)

    async def on_unknown_sender(msg: InboundMessage, raw_body: bytes, headers: dict) -> None:
        # resolve_tenant_alias only returns non-None for status=="active", so
        # app.py routes here for BOTH truly-new senders and known-but-disabled
        # ones (e.g. offboarded). Distinguish them before provisioning --
        # otherwise an offboarded tenant would get silently re-provisioned
        # the next time they text.
        existing = load_tenant_registry(platform_dir).get(msg.wa_id)
        if existing is not None:
            await send_text_message(
                meta_client, meta.phone_number_id, meta.access_token, msg.wa_id,
                account_disabled(existing.language),
            )
            return

        await send_text_message(
            meta_client, meta.phone_number_id, meta.access_token, msg.wa_id, welcome_provisioning()
        )
        tenant = await provision_new_tenant(
            platform_dir, install_root, config_templates_dir, config_toml_path,
            meta, zeroclaw_client, msg.wa_id,
        )
        await send_text_message(
            meta_client, meta.phone_number_id, meta.access_token, msg.wa_id,
            welcome_ready(TRIAL_CREDIT_USD, tenant.language),
        )

    async def on_insufficient_balance(tenant_alias: str, msg: InboundMessage) -> None:
        _pending, topup_link = create_pending_topup(platform_dir, tenant_alias, owner_wallet, usdc_mint)
        await send_text_message(
            meta_client, meta.phone_number_id, meta.access_token, msg.wa_id,
            insufficient_balance(topup_link),
        )

    return GateDependencies(
        resolve_tenant=resolve_tenant,
        check_balance=check_balance,
        on_unknown_sender=on_unknown_sender,
        on_insufficient_balance=on_insufficient_balance,
        zeroclaw_base_url="http://127.0.0.1:42617",
        http_client=zeroclaw_client,
    )
