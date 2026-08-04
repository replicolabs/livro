#!/bin/bash
# bash, not POSIX sh -- `wait -n` (wait for whichever child exits first)
# below is a bash-ism dash doesn't support.
# Starts ZeroClaw (loopback only) and the gate (public port) as sibling
# processes in one container, per the approved plan's deployment topology.
#
# ZeroClaw binds 127.0.0.1 ONLY -- confirmed live this session that
# /admin/reload is unconditionally allowed for loopback callers with no
# extra auth (admin_reload_gate, crates/zeroclaw-gateway/src/lib.rs:3849),
# while a remote caller needs gateway.allow_remote_admin=true plus pairing.
# Co-locating and binding loopback avoids that whole extra credential
# surface, AND means ZeroClaw is not reachable from any other Railway
# service either, private network included -- it isn't listening on any
# interface a network packet from outside this container can reach.
set -e

ZEROCLAW_CONFIG_DIR="${ZEROCLAW_CONFIG_DIR:-/data/zeroclaw}"
export ZEROCLAW_CONFIG_DIR
mkdir -p "$ZEROCLAW_CONFIG_DIR"

CONFIG_TOML="$ZEROCLAW_CONFIG_DIR/config.toml"
touch "$CONFIG_TOML"

# Every tenant's agent block (written by gate/provisioning.py) hardcodes
# model_provider = "anthropic.default", but the gate only ever appends
# per-tenant blocks -- nothing seeds the shared [providers.models.*] table
# itself. Confirmed live: setting only the api_key leaf via the
# ZEROCLAW_PROVIDERS__MODELS__ANTHROPIC__DEFAULT__API_KEY env var does NOT
# vivify a missing table -- ZeroClaw's env overlay fills in an existing
# path, it doesn't create a new map entry from a leaf alone, so every
# tenant's model_provider reference dangled (schema.rs's
# dangling_reference check) and no agent turn could ever invoke the model.
# Seed the table here, once, before ZeroClaw's first read -- idempotent so
# re-deploys and existing volumes are unaffected -- and leave api_key out
# of the file entirely; the env var still supplies it on top of this.
if ! grep -q '^\[providers\.models\.anthropic\.default\]' "$CONFIG_TOML"; then
    cat >> "$CONFIG_TOML" <<'EOF'

[providers.models.anthropic.default]
enabled = true
model = "claude-sonnet-5"
EOF
fi

# Same class of bug, same fix: every tenant's agent block hardcodes
# skill_bundles = ["livro"], but nothing ever seeds the shared
# [skill_bundles.livro] table it references either -- confirmed live,
# a second dangling_reference only surfaced once the model_provider one
# above was fixed (zeroclaw_runtime::skills logged "skipping skill
# bundle: [skill_bundles.] is not configured" and dropped it silently).
# directory is relative to the process CWD (WORKDIR /app in the
# Dockerfile), matching where shared/ is COPied.
if ! grep -q '^\[skill_bundles\.livro\]' "$CONFIG_TOML"; then
    cat >> "$CONFIG_TOML" <<'EOF'

[skill_bundles.livro]
directory = "shared/skills/livro"
EOF
fi

# Third and last of the same class: agent_block["runtime_profile"] =
# "default" (provisioning.py) references [runtime_profiles.default],
# never seeded either. RuntimeProfileConfig is #[serde(default)] on every
# field, so an empty table is a valid, fully-default profile -- just
# needs to exist.
if ! grep -q '^\[runtime_profiles\.default\]' "$CONFIG_TOML"; then
    cat >> "$CONFIG_TOML" <<'EOF'

[runtime_profiles.default]
EOF
fi

# [sop] is missing too -- not a dangling_reference (sops_dir is a path,
# not a cross-table alias) so it fails silently rather than logging a
# validation warning: no sops_dir means the cron-triggered SOPs
# (watch_payment, monthly_reminder, threshold_watch, backup_export) just
# never run. config/config.toml.example documents sops_dir MUST be
# absolute -- it resolves against the process's CWD at the moment each
# `zeroclaw` command runs, not the install root -- so use the same
# absolute path the Dockerfile COPies sops/ to (WORKDIR /app).
if ! grep -q '^\[sop\]' "$CONFIG_TOML"; then
    cat >> "$CONFIG_TOML" <<'EOF'

[sop]
sops_dir = "/app/sops"
maintenance_interval_secs = 60
max_concurrent_total = 20
EOF
fi

# --verbose is a GLOBAL flag (must precede the subcommand, confirmed
# against src/main.rs -- `#[arg(short, long, global = true)] verbose: bool`
# on the top-level Cli struct, not Daemon's own args). Without it, ZeroClaw
# routes every tracing event to an internal trace file only -- confirmed
# live this session that this is why nothing ZeroClaw-side (agent turns,
# provider errors) ever showed up in Railway's stdout-captured deploy logs,
# even though the gate's own forwards were succeeding.
zeroclaw --verbose daemon --host 127.0.0.1 --port 42617 &
ZEROCLAW_PID=$!

uvicorn gate.app:app --host 0.0.0.0 --port "${PORT:-8000}" --app-dir /app &
GATE_PID=$!

# Railway sends SIGTERM on redeploy/stop -- forward it to both children so
# neither is orphaned when the container shuts down.
term_handler() {
    kill -TERM "$ZEROCLAW_PID" "$GATE_PID" 2>/dev/null || true
    wait "$ZEROCLAW_PID" "$GATE_PID" 2>/dev/null || true
    exit 0
}
trap term_handler TERM INT

wait -n "$ZEROCLAW_PID" "$GATE_PID"
# If either process exits on its own (crash), bring the whole container
# down rather than limping along with only half the system running.
term_handler
