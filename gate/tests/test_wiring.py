"""Covers the one piece of production wiring with real branching logic
worth testing directly: on_unknown_sender must distinguish a truly-new
wa_id (provision) from a known-but-disabled one (offboarded tenant texting
again) -- both resolve_tenant_alias to None, since it only returns
non-None for status=="active".
"""
from datetime import datetime, timezone

import pytest

from gate.provisioning import MetaCredentials
from gate.tenant_lookup import append_tenant_record
from platform_ledger.records import TenantRecord


META = MetaCredentials(
    phone_number_id="123456", access_token="tok", verify_token="verify", app_secret="secret"
)


def _set_env(monkeypatch, tmp_path):
    platform_dir = tmp_path / "platform"
    install_root = tmp_path / "install"
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "app_settings.json.example").write_text("{}")
    (templates_dir / "user_preferences.json.example").write_text('{"language": "pt-BR"}')
    config_path = install_root / "config.toml"
    install_root.mkdir(parents=True)
    config_path.write_text("")

    monkeypatch.setenv("LIVRO_PLATFORM_DIR", str(platform_dir))
    monkeypatch.setenv("LIVRO_INSTALL_ROOT", str(install_root))
    monkeypatch.setenv("LIVRO_CONFIG_TEMPLATES_DIR", str(templates_dir))
    monkeypatch.setenv("LIVRO_CONFIG_TOML_PATH", str(config_path))
    monkeypatch.setenv("LIVRO_OWNER_WALLET", "OwnerWa11etAddre55")
    monkeypatch.setenv("LIVRO_USDC_MINT", "MintAddre55")
    monkeypatch.setenv("LIVRO_META_PHONE_NUMBER_ID", META.phone_number_id)
    monkeypatch.setenv("LIVRO_META_ACCESS_TOKEN", META.access_token)
    monkeypatch.setenv("LIVRO_GATE_VERIFY_TOKEN", META.verify_token)
    monkeypatch.setenv("LIVRO_META_APP_SECRET", META.app_secret)
    return platform_dir


@pytest.mark.asyncio
async def test_on_unknown_sender_sends_account_disabled_for_offboarded_tenant(monkeypatch):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        platform_dir = _set_env(monkeypatch, Path(tmp))

        append_tenant_record(platform_dir, TenantRecord(
            tenant_id="t_dead", wa_id="5511999999999", agent_alias="t_dead",
            workspace_dir="/x", provisioned_at=datetime.now(timezone.utc),
            status="offboarded",
        ))

        from gate import wiring

        sent = []

        async def fake_send(client, phone_number_id, access_token, to_wa_id, text, base_url=None):
            sent.append((to_wa_id, text))

        monkeypatch.setattr(wiring, "send_text_message", fake_send)

        deps = wiring.build_production_dependencies()
        from gate.parsing import InboundMessage

        msg = InboundMessage(
            wa_id="5511999999999", message_id="m1",
            phone_number_id=META.phone_number_id, message_type="text",
        )
        await deps.on_unknown_sender(msg, b"{}", {})

        # exactly one message sent (account_disabled), never provisioning's
        # welcome_provisioning/welcome_ready pair
        assert len(sent) == 1
        assert "encerrada" in sent[0][1] or "closed" in sent[0][1]

        # and no new tenant was provisioned for this wa_id
        from gate.tenant_lookup import load_tenant_registry
        registry = load_tenant_registry(platform_dir)
        assert registry["5511999999999"].status == "offboarded"
        assert registry["5511999999999"].tenant_id == "t_dead"


@pytest.mark.asyncio
async def test_on_unknown_sender_provisions_truly_new_wa_id(monkeypatch):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        platform_dir = _set_env(monkeypatch, Path(tmp))

        from gate import wiring

        sent = []

        async def fake_send(client, phone_number_id, access_token, to_wa_id, text, base_url=None):
            sent.append((to_wa_id, text))

        monkeypatch.setattr(wiring, "send_text_message", fake_send)

        async def fake_reload(client, admin_base_url="http://127.0.0.1:42617"):
            class _Resp:
                status_code = 200
            return _Resp()

        import gate.tenant_lookup as tenant_lookup_mod
        monkeypatch.setattr(tenant_lookup_mod, "trigger_reload", fake_reload)

        deps = wiring.build_production_dependencies()
        from gate.parsing import InboundMessage

        msg = InboundMessage(
            wa_id="5511888888888", message_id="m1",
            phone_number_id=META.phone_number_id, message_type="text",
        )
        await deps.on_unknown_sender(msg, b"{}", {})

        # welcome_provisioning + welcome_ready, both sent, tenant now active
        assert len(sent) == 2
        from gate.tenant_lookup import load_tenant_registry
        registry = load_tenant_registry(platform_dir)
        assert registry["5511888888888"].status == "active"
