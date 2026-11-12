#!/usr/bin/env bash
#
# Resiliency scenario: signal / pause battery.
#
# Each phase injects a different kind of signal-driven disturbance on a
# master or minion container, then calls ``assert_reconnect`` to verify
# every minion in $MINION_IDS answers ``test.ping`` within
# $RECONNECT_WINDOW_SEC and that fd/rss haven't ballooned.
#
# Phases are independent: a failure in one does NOT skip the rest.  The
# script exits 0 only if every phase ran to "recovered"; otherwise 1.
#
# Phases:
#   1. signal_sigstop_master_30s      -- SIGSTOP primary master 30s then SIGCONT
#                                        (simulates a short GC / stop-the-world)
#   2. signal_sigstop_master_120s     -- same but 120s (past master_alive_interval)
#   3. signal_sigstop_minion          -- SIGSTOP first minion 60s then SIGCONT
#   4. signal_sighup_master           -- docker kill -s HUP (config reload)
#   5. signal_sigusr1_master          -- SIGUSR1 dumps internal state; must not crash
#   6. signal_kill_mworker            -- SIGKILL one MWorker-; master should respawn
#   7. signal_kill_publisher          -- SIGKILL PubServerChannel/EventPublisher child
#   8. signal_rolling_sigstop_cluster -- cluster3/multimaster: SIGSTOP each master
#                                        in turn 60s, SIGCONT in reverse order.
#                                        Skipped on single-master topologies.
#
# Env knobs (with defaults):
#   SIGSTOP_SHORT_SEC     30   seconds to hold the short master SIGSTOP
#   SIGSTOP_LONG_SEC      120  seconds to hold the long master SIGSTOP
#   SIGSTOP_MINION_SEC    60   seconds to hold the minion SIGSTOP
#   SIGSTOP_ROLLING_SEC   60   per-master hold in the rolling cluster phase
#   INTER_PHASE_WAIT_SEC  15   seconds between phases
#
# Exit code: 0 if every phase recovered, 1 otherwise (but every phase is
# still attempted).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${SIGSTOP_SHORT_SEC:=$TIER_FIRSTMISS_SEC}"
: "${SIGSTOP_LONG_SEC:=$TIER_DEEPREC_SEC}"
: "${SIGSTOP_MINION_SEC:=$TIER_STANDARD_SEC}"
: "${SIGSTOP_ROLLING_SEC:=$TIER_STANDARD_SEC}"
: "${INTER_PHASE_WAIT_SEC:=$PACING_INTER_PHASE_SEC}"

MASTER_COUNT=0
for _m in $MASTERS; do MASTER_COUNT=$((MASTER_COUNT + 1)); done

OVERALL_RC=0

# Make a best-effort to leave no master in a stopped state on exit.  The
# individual phases send SIGCONT themselves; this trap is the belt and
# braces for a mid-script abort (Ctrl-C, set -e trip, docker daemon flake).
cleanup() {
    for m in $MASTERS; do
        docker kill -s CONT "$m" >/dev/null 2>&1 || true
    done
    for c in $MINION_CONTAINERS; do
        docker kill -s CONT "$c" >/dev/null 2>&1 || true
    done
    log "signal_pause: EXIT trap -- sent SIGCONT to all containers (best-effort)"
}
trap cleanup EXIT INT TERM

record_setup_error() {
    local scenario="$1" notes="$2"
    log "SETUP_ERROR '$scenario': $notes"
    record_result "$scenario" "setup_error" "-1" "0" "" "0" "0" "0" "$notes"
    OVERALL_RC=1
}

between_phases() {
    log "sleeping ${INTER_PHASE_WAIT_SEC}s before next phase"
    sleep "$INTER_PHASE_WAIT_SEC"
}

# ---------------------------------------------------------------------------
# Generic SIGSTOP/SIGCONT hold on a container.
#   $1 label   $2 container   $3 hold_seconds
# ---------------------------------------------------------------------------
phase_sigstop_hold() {
    local label="$1" container="$2" hold="$3"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (container=${container} hold=${hold}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker kill -s STOP "$container" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s STOP ${container} failed"
        return 1
    fi
    sleep "$hold"
    if ! docker kill -s CONT "$container" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s CONT ${container} failed"
        # Try one more time; a stuck SIGSTOP leaves the fleet in a bad state.
        docker kill -s CONT "$container" >/dev/null 2>&1 || true
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "hold=${hold}s"; then
        OVERALL_RC=1
        return 1
    fi
    return 0
}

# ---------------------------------------------------------------------------
# Phase 1: short SIGSTOP on primary master (GC-pause analogue)
# ---------------------------------------------------------------------------
phase_sigstop_hold "signal_sigstop_master_30s" "$PRIMARY_MASTER" "$SIGSTOP_SHORT_SEC"
between_phases

# ---------------------------------------------------------------------------
# Phase 2: long SIGSTOP on primary master (past master_alive_interval)
# ---------------------------------------------------------------------------
phase_sigstop_hold "signal_sigstop_master_120s" "$PRIMARY_MASTER" "$SIGSTOP_LONG_SEC"
between_phases

# ---------------------------------------------------------------------------
# Phase 3: SIGSTOP first minion
# ---------------------------------------------------------------------------
FIRST_MINION="$(printf '%s\n' $MINION_CONTAINERS | head -1)"
phase_sigstop_hold "signal_sigstop_minion" "$FIRST_MINION" "$SIGSTOP_MINION_SEC"
between_phases

# ---------------------------------------------------------------------------
# Phase 4: SIGHUP on primary master -- config reload, no restart.
# Minions should keep answering test.ping throughout.
# ---------------------------------------------------------------------------
phase_sighup_master() {
    local label="signal_sighup_master"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker kill -s HUP "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s HUP ${PRIMARY_MASTER} failed"
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}
phase_sighup_master
between_phases

# ---------------------------------------------------------------------------
# Phase 5: SIGUSR1 on primary master -- Salt dumps internal state.
# Verify the master doesn't crash and minions remain reachable.
# ---------------------------------------------------------------------------
phase_sigusr1_master() {
    local label="signal_sigusr1_master"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker kill -s USR1 "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s USR1 ${PRIMARY_MASTER} failed"
        return 1
    fi
    # Give Salt a moment to write its state dump; still inside the
    # RECONNECT_WINDOW so it counts as part of the fault.
    sleep 5
    # Container must still be running after the signal.
    local state
    state="$(docker inspect -f '{{.State.Running}}' "$PRIMARY_MASTER" 2>/dev/null || echo false)"
    if [ "$state" != "true" ]; then
        record_setup_error "$label" "${PRIMARY_MASTER} not Running=true after SIGUSR1"
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}
phase_sigusr1_master
between_phases

# ---------------------------------------------------------------------------
# Phase 6: SIGKILL one MWorker-* child; the master process manager must
# respawn it and the fleet must stay healthy.
# ---------------------------------------------------------------------------
phase_kill_mworker() {
    local label="signal_kill_mworker"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    # pkill -1 kills at most one matching pid; fall back to killing the
    # first match via a pgrep pipe if the pkill -1 flag is unsupported.
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        if pkill -1 -SIGKILL -f 'MWorker-' 2>/dev/null; then
            exit 0
        fi
        pid=\$(pgrep -f 'MWorker-' | head -1)
        if [ -z \"\$pid\" ]; then
            echo 'no MWorker- process found' >&2
            exit 2
        fi
        kill -KILL \"\$pid\"
    " >/dev/null 2>&1; then
        record_setup_error "$label" "could not SIGKILL an MWorker- child inside ${PRIMARY_MASTER}"
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}
phase_kill_mworker
between_phases

# ---------------------------------------------------------------------------
# Phase 7: SIGKILL the PubServerChannel / EventPublisher child.
# ---------------------------------------------------------------------------
phase_kill_publisher() {
    local label="signal_kill_publisher"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    # Try PubServerChannel first, then EventPublisher.  Either is a
    # supervisor-owned child that should respawn.
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        for pat in 'PubServerChannel' 'EventPublisher' 'Publisher'; do
            pid=\$(pgrep -f \"\$pat\" | head -1)
            if [ -n \"\$pid\" ]; then
                kill -KILL \"\$pid\" && echo \"killed pat=\$pat pid=\$pid\" && exit 0
            fi
        done
        echo 'no publisher process found' >&2
        exit 2
    " >/dev/null 2>&1; then
        record_setup_error "$label" "could not SIGKILL a publisher child inside ${PRIMARY_MASTER}"
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}
phase_kill_publisher
between_phases

# ---------------------------------------------------------------------------
# Phase 8: rolling SIGSTOP across every master (cluster3 / multimaster only).
# SIGSTOP each master in forward order holding $SIGSTOP_ROLLING_SEC each,
# then SIGCONT in reverse order to prove the fleet rides out a cascading
# pause front.
# ---------------------------------------------------------------------------
phase_rolling_sigstop_cluster() {
    local label="signal_rolling_sigstop_cluster"
    if [ "$MASTER_COUNT" -le 1 ]; then
        log "${label}: single-master topology, skipping"
        # Emit a skip row so the analyzer accounts for the phase
        # (mirrors cluster_faults.sh's record_skip pattern).
        record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" \
            "MASTER_COUNT=${MASTER_COUNT}; rolling phase requires >=2 masters"
        return 0
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (masters=${MASTER_COUNT} per_hold=${SIGSTOP_ROLLING_SEC}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    local stopped=""
    local m
    # Forward: SIGSTOP each in turn with the hold between.
    for m in $MASTERS; do
        log "${label}: SIGSTOP ${m}"
        if ! docker kill -s STOP "$m" >/dev/null 2>&1; then
            record_setup_error "$label" "docker kill -s STOP ${m} failed"
            # Resume any already-stopped masters.
            for already in $stopped; do
                docker kill -s CONT "$already" >/dev/null 2>&1 || true
            done
            return 1
        fi
        stopped="${m} ${stopped}"   # prepend so iteration gives reverse order
        sleep "$SIGSTOP_ROLLING_SEC"
    done
    # Reverse: SIGCONT in reverse order (LIFO).
    for m in $stopped; do
        log "${label}: SIGCONT ${m}"
        docker kill -s CONT "$m" >/dev/null 2>&1 || true
    done
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "masters=${MASTER_COUNT}"; then
        OVERALL_RC=1
    fi
}
phase_rolling_sigstop_cluster

log "signal_pause battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
