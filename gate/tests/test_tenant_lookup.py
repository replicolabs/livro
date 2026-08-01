import asyncio
from decimal import Decimal

import httpx
import pytest
from fastapi import FastAPI

from gate.balance import get_balance
from gate.provisioning import MetaCredentials
from gate.tenant_lookup import (
    append_tenant_record,
    load_tenant_registry,
    offboard_tenant,
    provision_new_tenant,
    resolve_tenant_alias,
)
from platform_ledger.records import TenantRecord
from datetime import datetime, timezone

META = MetaCredentials(
    phone_number_id="123456", access_token="tok", verify_token="verify", app_secret="secret"
)


def _mock_admin_client(reload_calls: list):
    app = FastAPI()

    @app.post("/admin/reload")
    async def reload_endpoint():
        reload_calls.append(True)
        return {"status": "reloading"}

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:42617")


def _setup(tmp_path):
    platform_dir = tmp_path / "platform"
    install_root = tmp_path / "install"
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "app_settings.json.example").write_text("{}")
    (templates_dir / "user_preferences.json.example").write_text('{"language": "pt-BR"}')
    config_path = install_root / "config.toml"
    install_root.mkdir(parents=True)
    config_path.write_text("")
    return platform_dir, install_root, templates_dir, config_path


@pytest.mark.asyncio
async def test_resolve_unknown_wa_id_returns_none(tmp_path):
    platform_dir, *_ = _setup(tmp_path)
    assert await resolve_tenant_alias(platform_dir, "5511999999999") is None


@pytest.mark.asyncio
async def test_provision_new_tenant_end_to_end(tmp_path):
    platform_dir, install_root, templates_dir, config_path = _setup(tmp_path)
    reload_calls = []
    admin_client = _mock_admin_client(reload_calls)

    tenant = await provision_new_tenant(
        platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511999999999"
    )

    assert tenant.wa_id == "5511999999999"
    assert tenant.status == "active"
    assert reload_calls == [True]  # reload was actually triggered

    # workspace exists
    assert (install_root / "agents" / tenant.tenant_id / "workspace" / "config").is_dir()

    # config.toml got the tenant's blocks
    assert f"[agents.{tenant.tenant_id}]" in config_path.read_text()

    # trial credit granted
    assert get_balance(platform_dir, tenant.tenant_id) == Decimal("1.00")

    # now resolvable
    assert await resolve_tenant_alias(platform_dir, "5511999999999") == tenant.tenant_id


@pytest.mark.asyncio
async def test_resolve_returns_none_for_non_active_status(tmp_path):
    platform_dir, *_ = _setup(tmp_path)
    append_tenant_record(platform_dir, TenantRecord(
        tenant_id="t_1", wa_id="5511999999999", agent_alias="t_1",
        workspace_dir="/x", provisioned_at=datetime.now(timezone.utc), status="suspended",
    ))
    assert await resolve_tenant_alias(platform_dir, "5511999999999") is None


@pytest.mark.asyncio
async def test_provision_same_wa_id_concurrently_only_provisions_once(tmp_path):
    """The race this test guards against: two messages from the SAME
    unrecognized number arriving close together must not allocate two
    different tenant_ids.
    """
    platform_dir, install_root, templates_dir, config_path = _setup(tmp_path)
    reload_calls = []
    admin_client = _mock_admin_client(reload_calls)

    results = await asyncio.gather(
        provision_new_tenant(platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511999999999"),
        provision_new_tenant(platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511999999999"),
    )

    assert results[0].tenant_id == results[1].tenant_id  # same tenant, not two
    assert len(load_tenant_registry(platform_dir)) == 1
    assert reload_calls == [True]  # only reloaded once, not twice


@pytest.mark.asyncio
async def test_provision_different_wa_ids_concurrently_each_get_distinct_tenant(tmp_path):
    platform_dir, install_root, templates_dir, config_path = _setup(tmp_path)
    reload_calls = []
    admin_client = _mock_admin_client(reload_calls)

    results = await asyncio.gather(
        provision_new_tenant(platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511111111111"),
        provision_new_tenant(platform_dir, install_root, templates_dir, config_path, META, admin_client, "5522222222222"),
    )

    assert results[0].tenant_id != results[1].tenant_id
    registry = load_tenant_registry(platform_dir)
    assert len(registry) == 2
    assert reload_calls == [True, True]  # serialized, one reload per new tenant here (no batching built)


@pytest.mark.asyncio
async def test_offboard_tenant_disables_config_and_appends_offboarded_record(tmp_path):
    platform_dir, install_root, templates_dir, config_path = _setup(tmp_path)
    reload_calls = []
    admin_client = _mock_admin_client(reload_calls)

    tenant = await provision_new_tenant(
        platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511999999999"
    )
    reload_calls.clear()

    offboarded = await offboard_tenant(platform_dir, config_path, admin_client, tenant)

    assert offboarded.status == "offboarded"
    assert offboarded.tenant_id == tenant.tenant_id
    assert offboarded.wa_id == tenant.wa_id
    assert reload_calls == [True]  # offboarding also triggers a reload

    # config blocks disabled, not deleted
    toml_text = config_path.read_text()
    assert f"[agents.{tenant.tenant_id}]" in toml_text
    assert f"[channels.whatsapp.{tenant.tenant_id}]" in toml_text
    import tomlkit as _tomlkit
    doc = _tomlkit.parse(toml_text)
    assert doc["agents"][tenant.tenant_id]["enabled"] is False
    assert doc["channels"]["whatsapp"][tenant.tenant_id]["enabled"] is False

    # last-record-wins registry now reflects offboarded, not active
    registry = load_tenant_registry(platform_dir)
    assert registry[tenant.wa_id].status == "offboarded"

    # no longer resolvable for routing
    assert await resolve_tenant_alias(platform_dir, "5511999999999") is None


@pytest.mark.asyncio
async def test_offboard_tenant_preserves_original_provisioned_at(tmp_path):
    platform_dir, install_root, templates_dir, config_path = _setup(tmp_path)
    admin_client = _mock_admin_client([])

    tenant = await provision_new_tenant(
        platform_dir, install_root, templates_dir, config_path, META, admin_client, "5511999999999"
    )
    offboarded = await offboard_tenant(platform_dir, config_path, admin_client, tenant)

    assert offboarded.provisioned_at == tenant.provisioned_at
