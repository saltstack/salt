#!/usr/bin/env bash
#
# Resiliency scenario: master restart battery.
#
# Phases (each independent; a failure in one does not short-circuit the rest):
#
#   1. master_restart_sigterm        -- docker stop (graceful SIGTERM + 30s grace)
#   2. master_restart_sigkill        -- docker kill --signal=KILL (no grace)
#   3. master_restart_docker_restart -- docker restart (stop + start, one cmd)
#   4. master_restart_rolling_<ctr>  -- restart every master sequentially
#                                       (skipped when |MASTERS| == 1)
#   5. master_restart_simultaneous   -- restart all masters in parallel
#                                       (skipped when |MASTERS| == 1)
#
# For every phase we:
#   - sample minion fd+rss baseline via sample_all_minions BEFORE the fault,
#     so the fd/rss deltas recorded by assert_reconnect are per-fault, not
#     cumulative across the battery
#   - inject the fault
#   - wait for the master container to be running again (docker inspect)
#   - call assert_reconnect which records one results.jsonl row
#
# Between phases we sleep $INTER_PHASE_WAIT_SEC so recovery for phase N does
# not bleed into the baseline captured at the start of phase N+1.
#
# Env tunables (all have defaults):
#   RESTART_IDLE_SEC       10   seconds between stop/kill and start
#   INTER_MASTER_WAIT_SEC  30   seconds between masters in the rolling phase
#   INTER_PHASE_WAIT_SEC   15   seconds between phases
#
# Exit code: 0 if every phase recovered, 1 otherwise (but every phase is
# still attempted).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${RESTART_IDLE_SEC:=10}"
: "${INTER_MASTER_WAIT_SEC:=30}"
: "${INTER_PHASE_WAIT_SEC:=15}"

# Count masters without arrays so `set -u` is happy and word-splitting is explicit.
MASTER_COUNT=0
for _m in $MASTERS; do MASTER_COUNT=$((MASTER_COUNT + 1)); done

OVERALL_RC=0

# Wait until `docker inspect` reports the container as running.  We do NOT
# use salt-run or any in-container Salt CLI here: during the fault window
# the master is down, so querying it would deadlock.
wait_container_running() {
    local container="$1"
    local deadline=$(( $(date +%s) + 120 ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        local state
        state="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo false)"
        if [ "$state" = "true" ]; then
            return 0
        fi
        sleep 1
    done
    log "wait_container_running: $container did not reach Running=true within 120s"
    return 1
}

# Record a setup_error row and bump OVERALL_RC when a phase can't even be run.
record_setup_error() {
    local scenario="$1" notes="$2"
    log "SETUP_ERROR '$scenario': $notes"
    record_result "$scenario" "setup_error" "-1" "0" "" "0" "0" "0" "$notes"
    OVERALL_RC=1
}

run_phase() {
    # $1 label, $2 pre-fault command string, $3 idle seconds, $4 post-fault command
    local label="$1" pre_cmd="$2" idle="$3" post_cmd="$4"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    log "phase '$label': fd_before=${fd_before} rss_before_kb=${rss_before}"
    fault_start=$(date +%s)
    log "phase '$label': pre_cmd: $pre_cmd"
    if ! eval "$pre_cmd"; then
        record_setup_error "$label" "pre_cmd failed: $pre_cmd"
        return 1
    fi
    sleep "$idle"
    log "phase '$label': post_cmd: $post_cmd"
    if ! eval "$post_cmd"; then
        record_setup_error "$label" "post_cmd failed: $post_cmd"
        return 1
    fi
    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
        return 1
    fi
    return 0
}

between_phases() {
    log "sleeping ${INTER_PHASE_WAIT_SEC}s before next phase"
    sleep "$INTER_PHASE_WAIT_SEC"
}

# --------------------------------------------------------------------------
# Phase 1: graceful SIGTERM (docker stop --time=30)
# --------------------------------------------------------------------------
run_phase \
    "master_restart_sigterm" \
    "docker stop --time=30 \"$PRIMARY_MASTER\" >/dev/null" \
    "$RESTART_IDLE_SEC" \
    "docker start \"$PRIMARY_MASTER\" >/dev/null && wait_container_running \"$PRIMARY_MASTER\""

between_phases

# --------------------------------------------------------------------------
# Phase 2: SIGKILL (no grace)
# --------------------------------------------------------------------------
run_phase \
    "master_restart_sigkill" \
    "docker kill --signal=KILL \"$PRIMARY_MASTER\" >/dev/null" \
    "$RESTART_IDLE_SEC" \
    "docker start \"$PRIMARY_MASTER\" >/dev/null && wait_container_running \"$PRIMARY_MASTER\""

between_phases

# --------------------------------------------------------------------------
# Phase 3: docker restart (one command; no explicit idle gap)
# --------------------------------------------------------------------------
# docker restart stops (SIGTERM + grace) then starts in one call; the
# "idle" sleep is 0 because the gap is encoded by docker itself.
run_phase \
    "master_restart_docker_restart" \
    "docker restart \"$PRIMARY_MASTER\" >/dev/null" \
    "0" \
    "wait_container_running \"$PRIMARY_MASTER\""

between_phases

# --------------------------------------------------------------------------
# Phase 4: rolling restart (skipped on single-master topologies)
# --------------------------------------------------------------------------
if [ "$MASTER_COUNT" -gt 1 ]; then
    for m in $MASTERS; do
        run_phase \
            "master_restart_rolling_${m}" \
            "docker restart \"$m\" >/dev/null" \
            "0" \
            "wait_container_running \"$m\""
        log "rolling: sleeping ${INTER_MASTER_WAIT_SEC}s before next master"
        sleep "$INTER_MASTER_WAIT_SEC"
    done
    between_phases
else
    log "rolling restart: only one master in topology, skipping"
fi

# --------------------------------------------------------------------------
# Phase 5: simultaneous restart of every master (skipped on single-master)
# --------------------------------------------------------------------------
if [ "$MASTER_COUNT" -gt 1 ]; then
    fd_before=0
    rss_before=0
    read -r fd_before rss_before < <(sample_all_minions)
    log "phase 'master_restart_simultaneous': fd_before=${fd_before} rss_before_kb=${rss_before}"
    fault_start=$(date +%s)
    pids=""
    for m in $MASTERS; do
        log "phase 'master_restart_simultaneous': docker restart $m (bg)"
        docker restart "$m" >/dev/null &
        pids="$pids $!"
    done
    sim_rc=0
    for p in $pids; do
        if ! wait "$p"; then
            sim_rc=1
        fi
    done
    if [ "$sim_rc" -ne 0 ]; then
        record_setup_error "master_restart_simultaneous" "one or more docker restart commands failed"
    else
        # Make sure every master is actually up before pinging.
        all_up=1
        for m in $MASTERS; do
            if ! wait_container_running "$m"; then
                all_up=0
            fi
        done
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        if [ "$all_up" -ne 1 ]; then
            record_setup_error "master_restart_simultaneous" "not all masters returned to Running=true"
        else
            if ! assert_reconnect "master_restart_simultaneous" "$fault_s" "$fd_before" "$rss_before" ""; then
                OVERALL_RC=1
            fi
        fi
    fi
else
    log "simultaneous restart: only one master in topology, skipping"
fi

log "master_restart battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
