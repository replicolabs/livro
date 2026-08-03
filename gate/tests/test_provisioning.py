import httpx
import pytest
import tomlkit

from gate.provisioning import (
    MetaCredentials,
    allocate_tenant_id,
    append_tenant_config,
    bootstrap_workspace,
    trigger_reload,
)

META = MetaCredentials(
    phone_number_id="123456",
    access_token="EAAtest-access-token",
    verify_token="my-verify-token",
    app_secret="my-app-secret",
)
WA_ID = "5511999999999"


def test_allocate_tenant_id_format():
    tid = allocate_tenant_id()
    assert tid.startswith("t_")
    assert len(tid) == len("t_") + 8


def test_allocate_tenant_id_is_unique():
    ids = {allocate_tenant_id() for _ in range(100)}
    assert len(ids) == 100


def test_bootstrap_workspace_creates_dirs_and_copies_templates(tmp_path):
    install_root = tmp_path / "install"
    templates_dir = tmp_path / "config_templates"
    templates_dir.mkdir()
    (templates_dir / "app_settings.json.example").write_text('{"solana_rpc_url": "x"}')
    (templates_dir / "user_preferences.json.example").write_text('{"language": "pt-BR"}')

    workspace = bootstrap_workspace(install_root, "t_abc12345", templates_dir)

    assert workspace == install_root / "agents" / "t_abc12345" / "workspace"
    assert (workspace / "config" / "app_settings.json").exists()
    assert (workspace / "config" / "user_preferences.json").exists()
    assert (workspace / "ledger").is_dir()
    assert (workspace / "backups").is_dir()
    assert '"language": "pt-BR"' in (workspace / "config" / "user_preferences.json").read_text()


def test_append_tenant_config_preserves_existing_content_and_comments(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "# Livro multi-tenant config\n"
        "# do not edit the header by hand\n"
        "\n"
        "[sop]\n"
        "sops_dir = \"/data/shared/sops\"\n"
    )

    append_tenant_config(config_path, "t_abc12345", META, WA_ID)

    result = config_path.read_text()
    assert "# Livro multi-tenant config" in result
    assert "# do not edit the header by hand" in result
    assert 'sops_dir = "/data/shared/sops"' in result  # untouched


def test_append_tenant_config_writes_correct_whatsapp_block(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    append_tenant_config(config_path, "t_abc12345", META, WA_ID)

    doc = tomlkit.parse(config_path.read_text())
    block = doc["channels"]["whatsapp"]["t_abc12345"]
    assert block["enabled"] is True
    assert block["phone_number_id"] == "123456"
    assert block["access_token"] == "EAAtest-access-token"
    assert block["verify_token"] == "my-verify-token"
    assert block["app_secret"] == "my-app-secret"
    assert list(block["allowed_numbers"]) == [f"+{WA_ID}"]


def test_append_tenant_config_writes_correct_agent_block(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    append_tenant_config(config_path, "t_abc12345", META, WA_ID)

    doc = tomlkit.parse(config_path.read_text())
    agent = doc["agents"]["t_abc12345"]
    assert agent["enabled"] is True
    assert list(agent["channels"]) == ["whatsapp.t_abc12345"]
    assert agent["model_provider"] == "anthropic.default"
    assert agent["risk_profile"] == "t_abc12345"
    assert agent["skill_bundles"] == ["livro"]


def test_append_tenant_config_writes_correct_peer_group_block(tmp_path):
    """The actual live allowlist gate for schema_version=3 configs is
    Config::peer_groups, not channels.whatsapp.<alias>.allowed_numbers --
    confirmed against running ZeroClaw source (channel_external_peers).
    Without this block every sender is silently dropped for every tenant.
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    append_tenant_config(config_path, "t_abc12345", META, WA_ID)

    doc = tomlkit.parse(config_path.read_text())
    group = doc["peer_groups"]["t_abc12345"]
    assert group["channel"] == "whatsapp.t_abc12345"
    assert list(group["agents"]) == ["t_abc12345"]
    assert list(group["external_peers"]) == [f"+{WA_ID}"]


def test_append_tenant_config_writes_correct_risk_profile_with_always_ask(tmp_path):
    """The corrected posture: shell/http_request go back to always_ask now
    that Cloud API actually supports request_approval, unlike Web mode.
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    append_tenant_config(config_path, "t_abc12345", META, WA_ID)

    doc = tomlkit.parse(config_path.read_text())
    risk = doc["risk_profiles"]["t_abc12345"]
    assert risk["level"] == "supervised"
    assert risk["workspace_only"] is True
    assert "shell" in risk["always_ask"]
    assert "http_request" in risk["always_ask"]
    assert "shell" not in risk["auto_approve"]


def test_append_tenant_config_second_tenant_does_not_clobber_first(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("")
    append_tenant_config(config_path, "t_first0001", META, "5511999999991")
    append_tenant_config(config_path, "t_second002", META, "5511999999992")

    doc = tomlkit.parse(config_path.read_text())
    assert "t_first0001" in doc["agents"]
    assert "t_second002" in doc["agents"]
    assert "t_first0001" in doc["channels"]["whatsapp"]
    assert "t_second002" in doc["channels"]["whatsapp"]


def test_append_tenant_config_result_reparses_cleanly(tmp_path):
    """Round-trip sanity: whatever tomlkit wrote must itself be valid TOML."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("[sop]\nsops_dir = \"/x\"\n")
    append_tenant_config(config_path, "t_abc12345", META, WA_ID)
    append_tenant_config(config_path, "t_xyz98765", META, "5511999999993")

    # tomlkit.parse already raises on invalid TOML; a plain re-parse is the assertion.
    reparsed = tomlkit.parse(config_path.read_text())
    assert reparsed["sop"]["sops_dir"] == "/x"


@pytest.mark.asyncio
async def test_trigger_reload_posts_to_admin_reload():
    from fastapi import FastAPI

    calls = []
    mock_app = FastAPI()

    @mock_app.post("/admin/reload")
    async def reload_endpoint():
        calls.append(True)
        return {"status": "reloading"}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app), base_url="http://127.0.0.1:42617"
    ) as client:
        response = await trigger_reload(client, admin_base_url="http://127.0.0.1:42617")

    assert response.status_code == 200
    assert calls == [True]
