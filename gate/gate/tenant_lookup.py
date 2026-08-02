"""wa_id -> tenant alias resolution, plus the provisioning orchestration for
a brand-new sender.

Concurrency: a single process-wide `asyncio.Lock` serializes the entire
provision-plus-reload sequence. This is simpler than the approved plan's
batching optimization (collect several near-simultaneous new signups into
one shared reload) and gives up some throughput at signup time in exchange
for obviously correct behavior -- provisioning is inherently rare/bursty,
not a hot path, so correctness matters more here than latency. Batching is
a legitimate later improvement, not built here. Cross-PROCESS safety (if
the gate ever runs more than one replica) is intentionally out of scope for
the same reason the approved plan calls for pinning the gate to exactly one
Railway replica -- an in-process lock alone cannot make config.toml
mutation safe across multiple writers.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import httpx

from ledger.serialization import to_json_line
from platform_ledger.records import CreditTopUp, TenantRecord

from gate.balance import append_topup
from gate.provisioning import (
    MetaCredentials,
    allocate_tenant_id,
    append_tenant_config,
    bootstrap_workspace,
    disable_tenant_config,
    trigger_reload,
)

# A handful of turns' worth of free credit -- granted automatically so a
# brand-new tenant never has to pay before seeing Livro work, the same
# onboarding-friction reasoning that ruled out BYOK (approved plan, Edge Cases).
TRIAL_CREDIT_USD = Decimal("1.00")

_provisioning_lock = asyncio.Lock()


def _tenants_path(platform_dir: Path) -> Path:
    return platform_dir / "tenants.jsonl"


def load_tenant_registry(platform_dir: Path) -> dict[str, TenantRecord]:
    """wa_id -> most recent TenantRecord. Append-only: a status change
    (e.g. offboarding) is a NEW record for the same wa_id, last one wins --
    never a mutation of the original, same discipline as every other Livro
    ledger.
    """
    path = _tenants_path(platform_dir)
    if not path.exists():
        return {}

    registry: dict[str, TenantRecord] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            registry[r["wa_id"]] = TenantRecord(
                tenant_id=r["tenant_id"],
                wa_id=r["wa_id"],
                agent_alias=r["agent_alias"],
                workspace_dir=r["workspace_dir"],
                provisioned_at=datetime.fromisoformat(r["provisioned_at"]),
                status=r["status"],
                language=r.get("language", "pt-BR"),
            )
    return registry


def append_tenant_record(platform_dir: Path, tenant: TenantRecord) -> None:
    platform_dir.mkdir(parents=True, exist_ok=True)
    with _tenants_path(platform_dir).open("a", encoding="utf-8") as f:
        f.write(to_json_line(tenant) + "\n")


async def resolve_tenant_alias(platform_dir: Path, wa_id: str) -> Optional[str]:
    """The real GateDependencies.resolve_tenant implementation: a known,
    active tenant resolves to their agent_alias; unknown or non-active
    (provisioning/suspended/offboarded) resolves to None so the caller
    treats them as not-yet-forwardable.
    """
    tenant = load_tenant_registry(platform_dir).get(wa_id)
    if tenant is None or tenant.status != "active":
        return None
    return tenant.agent_alias


async def provision_new_tenant(
    platform_dir: Path,
    install_root: Path,
    config_templates_dir: Path,
    config_toml_path: Path,
    meta: MetaCredentials,
    admin_client: httpx.AsyncClient,
    wa_id: str,
) -> TenantRecord:
    """Full provisioning sequence for a brand-new wa_id: allocate an id,
    bootstrap the workspace, mutate config.toml, grant a trial credit,
    trigger reload, record as active. Serialized by the process-wide lock
    so two near-simultaneous messages -- from the same OR different new
    senders -- never race on config.toml.
    """
    async with _provisioning_lock:
        # Re-check under the lock: a second message from the SAME wa_id
        # that arrived while the first was already provisioning must not
        # allocate a second tenant_id.
        existing = load_tenant_registry(platform_dir).get(wa_id)
        if existing is not None:
            return existing

        tenant_id = allocate_tenant_id()
        workspace = bootstrap_workspace(install_root, tenant_id, config_templates_dir)
        append_tenant_config(config_toml_path, tenant_id, meta, wa_id)

        trial = CreditTopUp(
            topup_id=f"trial_{tenant_id}",
            tenant_id=tenant_id,
            reference_key="trial",
            usdc_amount=Decimal("0"),
            credited_usd_balance_delta=TRIAL_CREDIT_USD,
            confirmed_at=datetime.now(timezone.utc),
            source="trial_grant",
        )
        append_topup(platform_dir, trial)

        await trigger_reload(admin_client)

        tenant = TenantRecord(
            tenant_id=tenant_id,
            wa_id=wa_id,
            agent_alias=tenant_id,
            workspace_dir=str(workspace),
            provisioned_at=datetime.now(timezone.utc),
            status="active",
        )
        append_tenant_record(platform_dir, tenant)
        return tenant


async def offboard_tenant(
    platform_dir: Path,
    config_toml_path: Path,
    admin_client: httpx.AsyncClient,
    tenant: TenantRecord,
) -> TenantRecord:
    """Disable (never delete) a tenant's config blocks and ledger history.
    Serialized by the same lock as provisioning -- disabling a tenant
    mutates the same config.toml every other tenant's blocks also live in,
    so it needs the same one-writer-at-a-time guarantee.
    """
    async with _provisioning_lock:
        disable_tenant_config(config_toml_path, tenant.tenant_id)
        await trigger_reload(admin_client)

        offboarded = TenantRecord(
            tenant_id=tenant.tenant_id,
            wa_id=tenant.wa_id,
            agent_alias=tenant.agent_alias,
            workspace_dir=tenant.workspace_dir,
            provisioned_at=tenant.provisioned_at,
            status="offboarded",
            language=tenant.language,
        )
        append_tenant_record(platform_dir, offboarded)
        return offboarded
