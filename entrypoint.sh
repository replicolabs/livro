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

zeroclaw daemon --host 127.0.0.1 --port 42617 &
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
