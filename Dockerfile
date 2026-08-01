# Livro multi-tenant deployment image: ZeroClaw (built from source with the
# full channel preset, since WhatsApp Cloud API -- channel-whatsapp-cloud --
# is a separate compile-time feature from WhatsApp Web and is NOT included
# in the standard prebuilt binary; confirmed live this session, see
# DEVIATIONS.md) + the gate/billing service, co-located in one image per
# the approved plan's deployment topology (single service, ZeroClaw bound
# to loopback only, only the gate's port ever exposed).

# ── Stage 1: build ZeroClaw from source ──────────────────────────────────
FROM rust:1.97-bookworm AS zeroclaw-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 https://github.com/zeroclaw-labs/zeroclaw.git .

# --preset full resolves the exact "every channel" feature set from
# ZeroClaw's own feature registry (xtask generate features --selection all)
# at build time, rather than us hardcoding/duplicating that list here --
# if ZeroClaw's feature set changes, this Dockerfile doesn't need updating.
# --apps none: we don't need zerocode or other CLI apps in this image.
#
# No --prefix here -- confirmed live (a real deploy failure) that install.sh
# only redirects CARGO_HOME under PREFIX via `${CARGO_HOME:-$PREFIX/.cargo}`,
# which never fires because the official rust:*-bookworm image already
# exports CARGO_HOME=/usr/local/cargo. cargo install therefore always lands
# at $CARGO_HOME/bin regardless of --prefix, so the binary is copied from
# there below instead of pretending --prefix controls the install path.
RUN ./install.sh --source --preset full --skip-quickstart --apps none \
        --no-modify-path

# ── Stage 2: runtime image ───────────────────────────────────────────────
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=zeroclaw-builder /usr/local/cargo/bin/zeroclaw /usr/local/bin/zeroclaw

WORKDIR /app

# Shared, stateless code every tenant's agent references -- NOT copied
# per-tenant (gate/provisioning.py's own docstring explains why: avoids N
# drifting copies of identical code). Only workspace *state* is per-tenant,
# created at runtime under the volume-mounted data dir.
COPY shared/ /app/shared/
COPY sops/ /app/sops/
COPY tax_engine/ /app/tax_engine/
COPY rendering/ /app/rendering/
COPY trust/ /app/trust/
COPY ledger/ /app/ledger/
COPY platform_ledger/ /app/platform_ledger/
COPY gate/ /app/gate/
COPY config/ /app/config/

RUN pip install --no-cache-dir -e ./ledger -e ./platform_ledger -e ./gate

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Railway injects $PORT for the gate's public listener. ZeroClaw's gateway
# is never exposed -- it binds 127.0.0.1 only, inside entrypoint.sh -- so
# there is deliberately no second EXPOSE for it.
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
