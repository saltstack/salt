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
# The pytest fixture spawns this script with ``start_new_session=True``
# so the script is already its own session + process-group leader --
# every ``&`` subshell below inherits the same pgid.  Do NOT set job
# control (``set -m``): with ``-m`` on, bash puts each ``&`` into a
# fresh pgroup, which (a) breaks the fixture's teardown
# (``os.killpg(pgid, SIGTERM)`` would only reach this script, not the
# loop subshells -- they'd leak to init), and (b) breaks the leak-gate
# sampling settle in ``Topology.pause_workload`` (SIGSTOP on pgid
# would miss every active loop and sampling would race in-flight
# ``docker exec`` children).  ``kill 0`` below sends to our pgid,
# which under this no-job-control mode covers every subshell.

set -u

# PRIMARY_MASTER identifies the container to run ``docker exec`` loops
# against.  The pytest ``workload`` fixture exports ``MASTER`` (the
# ``topology.spec.primary_master`` string); older callers may still
# pass PRIMARY_MASTER directly.  Previously this script sourced
# ``lib/common.sh`` for a bash ``load_topology`` function, but the
# bash scaffolding was removed when the suite moved to pytest, so
# that source silently errored out and every workload loop ran with
# no $PRIMARY_MASTER -- meaning every "under load" fault scenario
# was actually unloaded.  Fix: accept $MASTER or $PRIMARY_MASTER and
# bail loudly if neither is set.
PRIMARY_MASTER="${PRIMARY_MASTER:-${MASTER:-}}"
if [ -z "$PRIMARY_MASTER" ]; then
    printf 'workload.sh: PRIMARY_MASTER (or MASTER) env must be set\n' >&2
    exit 2
fi

: "${PING_INTERVAL:=5}"
: "${GRAINS_INTERVAL:=15}"
: "${STATE_INTERVAL:=30}"
: "${RUNNER_INTERVAL:=20}"

wlog() { printf '[workload] %s %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# (Deliberately no ``set -m`` -- see rationale in the header comment.)

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
