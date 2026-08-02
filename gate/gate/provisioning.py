"""New-tenant provisioning: workspace bootstrap + config.toml mutation +
reload trigger. Field names below were verified LIVE against a running
ZeroClaw v0.8.3 instance this session (via `zeroclaw config set` /
`zeroclaw config list`), not guessed from docs -- see DEVIATIONS.md.

Two corrections folded in here versus the single-tenant WhatsApp Web
config (`config/config.toml.example`):

1. Cloud API credentials (phone_number_id/access_token/verify_token/
   app_secret), not session_path -- every tenant's block uses the SAME
   literal values, since there is only one real Meta WhatsApp Business
   number shared by all tenants; only the `<tenant_id>` alias differs.
2. `shell`/`http_request` go back to `always_ask` here (not the
   `auto_approve` the single-tenant Web-mode build was forced into).
   Confirmed live: `whatsapp_web.rs` never calls `request_approval` at all
   (zero occurrences of "approval" in that file), which is what silently
   auto-denied every gated tool call under Web mode. Cloud API's
   `whatsapp.rs:796` does implement `request_approval` -- the constraint
   that forced the workaround doesn't apply here, so tenants get the
   originally-intended tighter gating instead.

No workspace `dir` override is written -- ZeroClaw derives an agent's
workspace at `<install_root>/agents/<alias>/workspace/` automatically from
the alias (confirmed live: no `workspace.dir`/`workspace.path` field
exists in the schema), which is exactly the per-tenant layout this module
creates on disk, so the convention and the bootstrap agree without needing
an explicit override.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
import tomlkit


@dataclass(frozen=True)
class MetaCredentials:
    """The one real Meta WhatsApp Business number's credentials, shared
    verbatim by every tenant's [channels.whatsapp.<tenant_id>] block.
    """

    phone_number_id: str
    access_token: str
    verify_token: str
    app_secret: str


def allocate_tenant_id() -> str:
    """Opaque id, not the raw phone number -- avoids PII in config.toml
    paths and TOML table keys, which may end up in logs/backups.
    """
    return f"t_{uuid.uuid4().hex[:8]}"


def bootstrap_workspace(install_root: Path, tenant_id: str, config_templates_dir: Path) -> Path:
    """Create <install_root>/agents/<tenant_id>/workspace/{config,ledger,backups}
    and seed config/ from the shared .example templates -- the same
    templates and directory shape used by hand in the single-tenant build
    (SETUP.md Section 2), just per-tenant now.
    """
    workspace = install_root / "agents" / tenant_id / "workspace"
    (workspace / "config").mkdir(parents=True, exist_ok=True)
    (workspace / "ledger").mkdir(parents=True, exist_ok=True)
    (workspace / "backups").mkdir(parents=True, exist_ok=True)

    shutil.copy(
        config_templates_dir / "app_settings.json.example",
        workspace / "config" / "app_settings.json",
    )
    shutil.copy(
        config_templates_dir / "user_preferences.json.example",
        workspace / "config" / "user_preferences.json",
    )
    return workspace


def _ensure_table(parent, key: str):
    """tomlkit doesn't auto-vivify nested tables the way a plain dict
    would -- get-or-create, preserving whatever's already there.
    """
    if key not in parent:
        parent[key] = tomlkit.table()
    return parent[key]


def append_tenant_config(config_toml_path: Path, tenant_id: str, meta: MetaCredentials, wa_id: str) -> None:
    """Load config.toml with tomlkit (preserves comments/formatting
    elsewhere in the file), append this tenant's three blocks, write back.
    """
    doc = tomlkit.parse(config_toml_path.read_text(encoding="utf-8"))

    channels = _ensure_table(doc, "channels")
    whatsapp = _ensure_table(channels, "whatsapp")
    whatsapp_block = tomlkit.table()
    whatsapp_block["enabled"] = True
    whatsapp_block["phone_number_id"] = meta.phone_number_id
    whatsapp_block["access_token"] = meta.access_token
    whatsapp_block["verify_token"] = meta.verify_token
    whatsapp_block["app_secret"] = meta.app_secret
    # ZeroClaw's WhatsApp channel silently drops any sender not on this
    # list (zeroclaw-channels/src/whatsapp.rs:234, confirmed live -- it
    # logs a WARN to its internal trace file only, invisible without
    # --verbose, which cost real debugging time). Scoping this to just the
    # tenant's own wa_id is also genuine defense-in-depth for hard
    # isolation: even if the gate's alias routing were ever tricked into
    # forwarding a different sender's message to this alias, ZeroClaw
    # itself still refuses anyone but this tenant.
    whatsapp_block["allowed_numbers"] = [f"+{wa_id}"]
    whatsapp[tenant_id] = whatsapp_block

    agents = _ensure_table(doc, "agents")
    agent_block = tomlkit.table()
    agent_block["enabled"] = True
    agent_block["channels"] = [f"whatsapp.{tenant_id}"]
    agent_block["model_provider"] = "anthropic.default"
    agent_block["risk_profile"] = tenant_id
    agent_block["runtime_profile"] = "default"
    agent_block["skill_bundles"] = ["livro"]
    agents[tenant_id] = agent_block

    risk_profiles = _ensure_table(doc, "risk_profiles")
    risk_block = tomlkit.table()
    risk_block["level"] = "supervised"
    risk_block["require_approval_for_medium_risk"] = True
    risk_block["block_high_risk_commands"] = True
    risk_block["workspace_only"] = True
    risk_block["auto_approve"] = ["file_read", "memory_recall", "ask_user", "content_search", "glob_search"]
    risk_block["always_ask"] = ["shell", "http_request", "escalate_to_human"]
    risk_profiles[tenant_id] = risk_block

    config_toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def disable_tenant_config(config_toml_path: Path, tenant_id: str) -> None:
    """Offboarding: set enabled=false on the tenant's channel and agent
    blocks. Never delete them -- a config block is effectively a record
    too, and this project never removes append-only history (same
    reasoning as every other Livro ledger). Raises KeyError if the tenant
    isn't present, since disabling a tenant that was never provisioned is
    a caller bug, not a no-op to swallow silently.
    """
    doc = tomlkit.parse(config_toml_path.read_text(encoding="utf-8"))
    doc["channels"]["whatsapp"][tenant_id]["enabled"] = False
    doc["agents"][tenant_id]["enabled"] = False
    config_toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")


async def trigger_reload(client: httpx.AsyncClient, admin_base_url: str = "http://127.0.0.1:42617") -> httpx.Response:
    """POST /admin/reload -- loopback-only per confirmed source
    (admin_reload_gate, crates/zeroclaw-gateway/src/lib.rs:3849, test
    admin_reload_gate_loopback_always_allowed at line 7239), which is
    exactly why the gate and ZeroClaw are co-located on one Railway
    service rather than split across two with private networking.
    """
    return await client.post(f"{admin_base_url}/admin/reload")
