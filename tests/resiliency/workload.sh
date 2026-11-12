#!/bin/bash
# Background workload generator for the Salt resiliency test suite.
#
# This is deliberately LIGHTER than tests/monitoring/stress_test.sh --
# resiliency scenarios want enough traffic to exercise the master's
# request/pub/event paths while faults are injected, NOT a saturation
# test.  Four loops run concurrently under a shared process group so the
# orchestrator can tear the whole thing down via ``kill -- -<pgid>``.
#
# Env knobs (with defaults):
#   PING_INTERVAL     5   -- seconds between ``test.ping`` sweeps
#   GRAINS_INTERVAL   15  -- seconds between async ``grains.items``
#   STATE_INTERVAL    30  -- seconds between async empty ``state.apply``
#   RUNNER_INTERVAL   20  -- seconds between async ``manage.status`` runs
#
# Every CLI call is wrapped in ``|| true`` -- during a fault scenario
# (network choke, master restart, etc.) transient CLI errors are
# EXPECTED and must not kill the generator loop.
#
# Install the loops under a new process group (``set -m``) and trap
# SIGINT/SIGTERM to ``kill 0`` the group.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

load_topology

: "${PING_INTERVAL:=5}"
: "${GRAINS_INTERVAL:=15}"
: "${STATE_INTERVAL:=30}"
: "${RUNNER_INTERVAL:=20}"

wlog() { printf '[workload] %s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# Ensure we're session leader for our subprocesses so ``kill 0`` reaches
# every background loop regardless of how they fork.
set -m

PIDS=()

shutdown() {
    wlog "received signal -- tearing down loops"
    # Kill the whole process group (ourselves + every background loop).
    # Redirect in case we race with already-exited children.
    kill 0 2>/dev/null || true
    exit 0
}
trap shutdown INT TERM

wlog "starting on TOPOLOGY=${TOPOLOGY:-unknown} PRIMARY_MASTER=${PRIMARY_MASTER}"
wlog "intervals: ping=${PING_INTERVAL}s grains=${GRAINS_INTERVAL}s state=${STATE_INTERVAL}s runner=${RUNNER_INTERVAL}s"

# ---- loop 1: synchronous test.ping with a short timeout ----
(
    while true; do
        docker exec "$PRIMARY_MASTER" salt --timeout=10 '*' test.ping >/dev/null 2>&1 || true
        sleep "$PING_INTERVAL"
    done
) &
PIDS+=($!)
wlog "ping loop pid=$!"

# ---- loop 2: async grains.items (bulk return path) ----
(
    while true; do
        docker exec "$PRIMARY_MASTER" salt --async '*' grains.items >/dev/null 2>&1 || true
        sleep "$GRAINS_INTERVAL"
    done
) &
PIDS+=($!)
wlog "grains loop pid=$!"

# ---- loop 3: async empty state.apply (compiler + fileserver path) ----
(
    while true; do
        docker exec "$PRIMARY_MASTER" salt --async '*' state.apply >/dev/null 2>&1 || true
        sleep "$STATE_INTERVAL"
    done
) &
PIDS+=($!)
wlog "state loop pid=$!"

# ---- loop 4: async runner manage.status (runner + job-cache path) ----
(
    while true; do
        docker exec "$PRIMARY_MASTER" salt-run --async manage.status >/dev/null 2>&1 || true
        sleep "$RUNNER_INTERVAL"
    done
) &
PIDS+=($!)
wlog "runner loop pid=$!"

wlog "all loops started; pids=${PIDS[*]}; pgid=$$"
wlog "stop with: kill -TERM -- -$$   (or: kill ${PIDS[*]})"

# Wait for any child to exit; if one dies unexpectedly, keep the rest
# running and just log.  Only SIGINT/SIGTERM (via trap) tears everything
# down cleanly.
while true; do
    if ! wait -n 2>/dev/null; then
        # wait -n with no remaining children returns non-zero; exit
        # gracefully in that case.
        if [ "$(jobs -rp | wc -l)" -eq 0 ]; then
            wlog "all loops have exited; shutting down"
            exit 0
        fi
    fi
done
