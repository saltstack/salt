#!/bin/bash
# Minion churn resiliency scenarios.
#
# Each phase injects a different kind of minion-side disruption and then
# calls ``assert_reconnect`` to verify every minion in $MINION_IDS answers
# ``test.ping`` within $RECONNECT_WINDOW_SEC and that fd/rss haven't
# ballooned across the fault window.
#
# Phases are independent: a failure in one does NOT skip the rest.  The
# script exits 0 only if every phase ran to "recovered"; otherwise 1.
#
# Env knobs (with defaults):
#   INTER_MINION_WAIT_SEC   20  -- pause between restarts in the rolling phase
#   STOP_DURATION_SEC       60  -- hard-pause duration for phase 5
#   KILL_RESTART_DELAY_SEC   2  -- pause between kill and start in phase 4
#
# Trap on EXIT leaves all containers running; the orchestrator owns
# compose teardown, this scenario must not ``docker rm`` anything.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${INTER_MINION_WAIT_SEC:=20}"
: "${STOP_DURATION_SEC:=60}"
: "${KILL_RESTART_DELAY_SEC:=2}"

# Track per-phase success; we do NOT short-circuit on first failure.
OVERALL_RC=0

cleanup() {
    # Deliberately non-destructive: the orchestrator owns compose lifecycle.
    log "minion_churn: EXIT trap -- leaving containers running"
}
trap cleanup EXIT

# Run a phase: snapshot fd/rss baseline, invoke the body, then assert.
# $1  phase label
# $2+ body command(s) to run (a shell function name + args)
run_phase() {
    local label="$1"; shift
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    local phase_start phase_end fault_s
    phase_start=$(date +%s)
    if ! "$@"; then
        log "phase ${label}: fault injection returned non-zero (continuing to assert anyway)"
    fi
    phase_end=$(date +%s)
    fault_s=$(( phase_end - phase_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 1: single-minion graceful restart
# ---------------------------------------------------------------------------
phase_single_restart() {
    local first
    first=$(printf '%s\n' $MINION_CONTAINERS | head -1)
    log "docker restart ${first}"
    docker restart "$first" >/dev/null
}

# ---------------------------------------------------------------------------
# Phase 2: rolling restart -- one at a time with a pause between each,
# asserting reconnect after every step.  Proves the master's auth path
# handles sequential re-key events without wedging the fleet.
# ---------------------------------------------------------------------------
phase_rolling_restart() {
    for m in $MINION_CONTAINERS; do
        local fd_before rss_before
        read -r fd_before rss_before < <(sample_all_minions)
        local label="minion_churn_rolling_${m}"
        log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
        local phase_start phase_end fault_s
        phase_start=$(date +%s)
        log "docker restart ${m}"
        docker restart "$m" >/dev/null || true
        sleep "$INTER_MINION_WAIT_SEC"
        phase_end=$(date +%s)
        fault_s=$(( phase_end - phase_start ))
        if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before"; then
            OVERALL_RC=1
        fi
    done
}

# ---------------------------------------------------------------------------
# Phase 3: simultaneous restart of every minion
# ---------------------------------------------------------------------------
phase_simultaneous_restart() {
    local pids=()
    for m in $MINION_CONTAINERS; do
        log "docker restart ${m} &"
        docker restart "$m" >/dev/null &
        pids+=($!)
    done
    for p in "${pids[@]}"; do
        wait "$p" || true
    done
}

# ---------------------------------------------------------------------------
# Phase 4: kill-9 one minion then restart it.  Catches cases where the
# minion vanishes WITHOUT sending a ``minion/disconnect`` event -- the
# master must still clean up the stale connection and accept the new auth.
#
# NOTE on docker signal delivery: ``docker kill --signal=KILL`` sends SIGKILL
# to PID 1 inside the container.  With a shell/supervisor as PID 1, this
# tears down the whole container (same visible effect as ``docker kill``
# with no flag).  If the container's PID 1 traps or re-execs, SIGKILL is
# un-trappable so the container still dies.  Either way ``docker start``
# brings it back.  If your docker version rejects ``--signal=KILL`` we fall
# back to a bare ``docker kill`` which defaults to SIGKILL.
# ---------------------------------------------------------------------------
phase_kill9() {
    local target
    target=$(printf '%s\n' $MINION_CONTAINERS | head -1)
    log "docker kill --signal=KILL ${target}"
    if ! docker kill --signal=KILL "$target" >/dev/null 2>&1; then
        log "docker kill --signal=KILL not accepted; falling back to 'docker kill ${target}'"
        docker kill "$target" >/dev/null || true
    fi
    sleep "$KILL_RESTART_DELAY_SEC"
    log "docker start ${target}"
    docker start "$target" >/dev/null || true
}

# ---------------------------------------------------------------------------
# Phase 5: hard pause -- stop one minion container for $STOP_DURATION_SEC,
# then start it again.  Longer gap than a restart, so the master should
# have fully timed out the old connection before re-auth.
# ---------------------------------------------------------------------------
phase_stop_start() {
    local target
    target=$(printf '%s\n' $MINION_CONTAINERS | head -1)
    log "docker stop --time=30 ${target} (then sleep ${STOP_DURATION_SEC}s)"
    docker stop --time=30 "$target" >/dev/null || true
    sleep "$STOP_DURATION_SEC"
    log "docker start ${target}"
    docker start "$target" >/dev/null || true
}

# ---------------------------------------------------------------------------
# Phase 6: multimaster-hothot ONLY.  Restart one of the two masters AND
# the (single) minion simultaneously; the minion must re-establish BOTH
# legs of its hot-hot connection.  For any other topology, record a
# ``skipped_for_topology`` result and move on.
# ---------------------------------------------------------------------------
phase_hothot_both_restart() {
    local label="minion_churn_hothot_both_restart"
    if [ "${TOPOLOGY:-}" != "multimaster-hothot" ]; then
        log "phase ${label}: skipped (TOPOLOGY=${TOPOLOGY:-unset} is not multimaster-hothot)"
        record_result "$label" "recovered" "0" "0" "" "0" "0" "0" "skipped_for_topology"
        return 0
    fi

    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"

    local master_target
    master_target=$(printf '%s\n' $MASTERS | head -1)
    local minion_target
    minion_target=$(printf '%s\n' $MINION_CONTAINERS | head -1)

    local phase_start phase_end fault_s
    phase_start=$(date +%s)
    log "docker restart ${master_target} & docker restart ${minion_target} &"
    docker restart "$master_target" >/dev/null &
    local mp=$!
    docker restart "$minion_target" >/dev/null &
    local np=$!
    wait "$mp" || true
    wait "$np" || true
    phase_end=$(date +%s)
    fault_s=$(( phase_end - phase_start ))

    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "both_legs_required"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Drive the battery
# ---------------------------------------------------------------------------
log "minion_churn: starting on TOPOLOGY=${TOPOLOGY:-unknown}"
log "minion_churn: MINION_CONTAINERS='${MINION_CONTAINERS}' PRIMARY_MASTER=${PRIMARY_MASTER}"

run_phase "minion_churn_single_restart"   phase_single_restart
# phase 2 handles its own per-step labels / assert_reconnect calls
phase_rolling_restart
run_phase "minion_churn_simultaneous"     phase_simultaneous_restart
run_phase "minion_churn_kill9"            phase_kill9
run_phase "minion_churn_stop_start"       phase_stop_start
phase_hothot_both_restart

if [ "$OVERALL_RC" -eq 0 ]; then
    log "minion_churn: ALL PHASES RECOVERED"
else
    log "minion_churn: ONE OR MORE PHASES FAILED (see $RESULTS_FILE)"
fi
exit "$OVERALL_RC"
