#!/usr/bin/env bash
#
# Resiliency scenario: marathon-outage battery.
#
# These phases hold the master unreachable for 30 minutes to 2 hours
# while the workload keeps hammering it.  They exist to catch
# long-outage auth-race bugs that short faults never reproduce --
# specifically the ``AsyncAuth._authenticate`` ``InvalidStateError``
# class where pending re-auth requests accumulate during the outage
# and then collide at the write site when the master returns, leaving
# the minion with ESTABLISHED sockets but a dead auth coroutine that
# never recovers (Broadcom Jira UBMVCFOPS-19586; upstream fix PR
# saltstack/salt#70772).
#
# These are EXPENSIVE: a nightly running all phases burns 3.5h of
# runner time by itself.  They are gated behind MARATHON_ENABLED=1 so
# the default nightly skips them, and record a ``skipped_for_topology``
# row (same accounting as cluster_faults.sh's topology gates) when
# disabled.
#
# Phases (each ends with assert_reconnect; OVERALL_RC accumulates):
#
#   1. marathon_outage_30m         docker stop master, workload runs,
#                                  30-minute hold, start, assert.
#   2. marathon_outage_60m         same, 60-minute hold.
#   3. marathon_outage_120m        same, 2-hour hold.  Requires
#                                  MARATHON_120M=1 as a separate opt-in
#                                  so the default enabled run doesn't
#                                  cost 3.5h by itself.
#   4. marathon_flap_during_auth_wave
#                                  30 iterations of (stop, 20s, start,
#                                  20s) while the minion is firing
#                                  concurrent ``saltutil.sync_all``
#                                  + ``test.ping`` -- the specific
#                                  recipe that triggers the
#                                  concurrent-auth race.
#
# Env knobs (with defaults):
#   MARATHON_ENABLED              0  set to 1 to run any phase
#   MARATHON_120M                 0  set to 1 to include the 2h phase
#   MARATHON_30M_SEC              1800
#   MARATHON_60M_SEC              3600
#   MARATHON_120M_SEC             7200
#   MARATHON_FLAP_CYCLES          30
#   MARATHON_FLAP_STOP_SEC        20
#   MARATHON_FLAP_UP_SEC          20
#   MARATHON_RECONNECT_WINDOW_SEC 600  how long to wait for the minion
#                                       to come back after a long
#                                       outage; default assert_reconnect
#                                       of 180s is too tight for 2h
#
# Exit code: 0 if every phase recovered or skipped, 1 otherwise.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${MARATHON_ENABLED:=0}"
: "${MARATHON_120M:=0}"
: "${MARATHON_30M_SEC:=$TIER_ACCUM_SEC}"
: "${MARATHON_60M_SEC:=$TIER_MARATHON_SEC}"
: "${MARATHON_120M_SEC:=$TIER_UPGRADE_SEC}"
: "${MARATHON_FLAP_CYCLES:=30}"
: "${MARATHON_FLAP_STOP_SEC:=$TIER_SUBKEEPALIVE_SEC}"
: "${MARATHON_FLAP_UP_SEC:=$TIER_SUBKEEPALIVE_SEC}"
: "${MARATHON_RECONNECT_WINDOW_SEC:=$RECOVER_MARATHON_SEC}"
: "${MARATHON_AUTH_WAVE_PIDS:=}"

# Scenario-local exit code: 0 = all phases recovered, 1 = at least
# one phase failed (recovery missed OR leak threshold exceeded).
OVERALL_RC=0

# Replace the shared reconnect window for the duration of marathon
# phases.  180s is too tight to let a minion that has queued thousands
# of retries settle back after 30-120 min of outage.
_MARATHON_PREV_RECONNECT_WINDOW="$RECONNECT_WINDOW_SEC"

cleanup() {
    # Belt-and-braces: restart any master that's still stopped so a
    # script abort doesn't leave the topology in a half-dead state.
    local m
    for m in $MASTERS; do
        docker start "$m" >/dev/null 2>&1 || true
    done
    # Kill any backgrounded auth-wave load generators.
    if [ -n "$MARATHON_AUTH_WAVE_PIDS" ]; then
        local pid
        for pid in $MARATHON_AUTH_WAVE_PIDS; do
            kill "$pid" 2>/dev/null || true
        done
    fi
    RECONNECT_WINDOW_SEC="$_MARATHON_PREV_RECONNECT_WINDOW"
    export RECONNECT_WINDOW_SEC
}
trap cleanup EXIT INT TERM

# Skip the whole scenario when MARATHON_ENABLED is off.  One skip row
# per phase so the analyzer's row count stays consistent across runs.
if [ "$MARATHON_ENABLED" != "1" ]; then
    log "MARATHON_ENABLED=0; emitting skip rows and exiting"
    for label in marathon_outage_30m marathon_outage_60m marathon_outage_120m marathon_flap_during_auth_wave; do
        record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" \
            "MARATHON_ENABLED=0 (set to 1 to opt in; multi-hour runtime)"
    done
    exit 0
fi

log "MARATHON_ENABLED=1; raising RECONNECT_WINDOW_SEC ${RECONNECT_WINDOW_SEC} -> ${MARATHON_RECONNECT_WINDOW_SEC}"
RECONNECT_WINDOW_SEC="$MARATHON_RECONNECT_WINDOW_SEC"
export RECONNECT_WINDOW_SEC

# -------------------------------------------------------------------------
# Helper: hold the master down for $1 seconds, log progress every 5 min,
# then start it back up.  Returns 0 if start succeeded, 1 otherwise.
# -------------------------------------------------------------------------
hold_master_down() {
    local hold_sec="$1"
    log "marathon: docker stop ${PRIMARY_MASTER} for ${hold_sec}s"
    if ! docker stop --time=30 "$PRIMARY_MASTER" >/dev/null 2>&1; then
        log "marathon: docker stop failed"
        return 1
    fi
    local end=$(( $(date +%s) + hold_sec ))
    while [ "$(date +%s)" -lt "$end" ]; do
        local remain=$(( end - $(date +%s) ))
        log "marathon: master down, ~${remain}s remaining"
        # 5-minute heartbeat, or finish the wait if less than 5 min.
        if [ "$remain" -gt 300 ]; then
            sleep 300
        else
            sleep "$remain"
        fi
    done
    log "marathon: docker start ${PRIMARY_MASTER}"
    if ! docker start "$PRIMARY_MASTER" >/dev/null 2>&1; then
        log "marathon: docker start failed"
        return 1
    fi
    return 0
}

# -------------------------------------------------------------------------
# Phase 1: 30-minute outage
# -------------------------------------------------------------------------
{
    label="marathon_outage_30m"
    hold="$MARATHON_30M_SEC"
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${hold}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    if hold_master_down "$hold"; then
        assert_reconnect "$label" "$hold" "$fd_before" "$rss_before" \
            "docker stop ${PRIMARY_MASTER} ${hold}s" || OVERALL_RC=1
    else
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "$hold" \
            "docker stop/start failed on ${PRIMARY_MASTER}"
        OVERALL_RC=1
    fi
    unset label hold fd_before rss_before
}

sleep "${INTER_PHASE_WAIT_SEC:-30}"

# -------------------------------------------------------------------------
# Phase 2: 60-minute outage
# -------------------------------------------------------------------------
{
    label="marathon_outage_60m"
    hold="$MARATHON_60M_SEC"
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${hold}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    if hold_master_down "$hold"; then
        assert_reconnect "$label" "$hold" "$fd_before" "$rss_before" \
            "docker stop ${PRIMARY_MASTER} ${hold}s" || OVERALL_RC=1
    else
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "$hold" \
            "docker stop/start failed on ${PRIMARY_MASTER}"
        OVERALL_RC=1
    fi
    unset label hold fd_before rss_before
}

sleep "${INTER_PHASE_WAIT_SEC:-30}"

# -------------------------------------------------------------------------
# Phase 3: 2-hour outage (opt-in: MARATHON_120M=1)
# -------------------------------------------------------------------------
{
    label="marathon_outage_120m"
    if [ "$MARATHON_120M" != "1" ]; then
        log "${label}: MARATHON_120M=0, skipping (set to 1 to enable the 2h phase)"
        record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" \
            "MARATHON_120M=0; enable with MARATHON_120M=1"
    else
        hold="$MARATHON_120M_SEC"
        read -r fd_before rss_before < <(sample_all_minions)
        log "---- phase: ${label} (hold=${hold}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
        if hold_master_down "$hold"; then
            assert_reconnect "$label" "$hold" "$fd_before" "$rss_before" \
                "docker stop ${PRIMARY_MASTER} ${hold}s" || OVERALL_RC=1
        else
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "$hold" \
                "docker stop/start failed on ${PRIMARY_MASTER}"
            OVERALL_RC=1
        fi
        unset hold fd_before rss_before
    fi
    unset label
}

sleep "${INTER_PHASE_WAIT_SEC:-30}"

# -------------------------------------------------------------------------
# Phase 4: flap-during-auth-wave
#
# The specific recipe that reproduces UBMVCFOPS-19586 inside minutes
# rather than hours: fire a concurrent auth-triggering call wave
# (saltutil.sync_all + test.ping in parallel) from each minion while
# the master flaps.  Pending auth requests accumulate during each
# stop window; the colliding result-set at the write site is what
# raises InvalidStateError on unfixed 3008.x.  On fixed code (#70772
# / #70713) every caller gets its own Future and the wave survives.
# -------------------------------------------------------------------------
{
    label="marathon_flap_during_auth_wave"
    read -r fd_before rss_before < <(sample_all_minions)
    local_cycles="$MARATHON_FLAP_CYCLES"
    total_est=$(( local_cycles * (MARATHON_FLAP_STOP_SEC + MARATHON_FLAP_UP_SEC) ))
    log "---- phase: ${label} (cycles=${local_cycles} stop_sec=${MARATHON_FLAP_STOP_SEC} up_sec=${MARATHON_FLAP_UP_SEC} est_total=${total_est}s) ----"

    # Background load generator: spawn one tight-loop auth-waver per
    # minion container.  Each one does a continuous
    #   salt-call --local saltutil.sync_all    (forces re-auth via the
    #                                            master even with
    #                                            --local because it
    #                                            fetches fileserver)
    #   salt-call test.ping                    (triggers an AsyncAuth
    #                                            path)
    # ... in parallel.  All calls are wrapped in || true so a transient
    # master-down doesn't break the loop.
    MARATHON_AUTH_WAVE_PIDS=""
    for m in $MINION_CONTAINERS; do
        (
            while true; do
                docker exec "$m" salt-call --local test.ping >/dev/null 2>&1 || true
                docker exec "$m" salt-call test.ping >/dev/null 2>&1 || true
                docker exec "$m" salt-call saltutil.sync_all >/dev/null 2>&1 || true
            done
        ) &
        MARATHON_AUTH_WAVE_PIDS="${MARATHON_AUTH_WAVE_PIDS} $!"
    done
    log "${label}: spawned $(printf '%s\n' $MARATHON_AUTH_WAVE_PIDS | wc -w) auth-waver pids: ${MARATHON_AUTH_WAVE_PIDS}"

    fault_start=$(date +%s)
    for i in $(seq 1 "$local_cycles"); do
        log "${label}: cycle ${i}/${local_cycles}: stop ${PRIMARY_MASTER} for ${MARATHON_FLAP_STOP_SEC}s"
        docker stop --time=5 "$PRIMARY_MASTER" >/dev/null 2>&1 || true
        sleep "$MARATHON_FLAP_STOP_SEC"
        log "${label}: cycle ${i}/${local_cycles}: start ${PRIMARY_MASTER}, hold ${MARATHON_FLAP_UP_SEC}s"
        docker start "$PRIMARY_MASTER" >/dev/null 2>&1 || true
        sleep "$MARATHON_FLAP_UP_SEC"
    done
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))

    # Terminate the auth wavers so assert_reconnect's test.ping isn't
    # fighting them for the master's MWorker pool.
    for pid in $MARATHON_AUTH_WAVE_PIDS; do
        kill "$pid" 2>/dev/null || true
    done
    MARATHON_AUTH_WAVE_PIDS=""
    sleep 5

    assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
        "cycles=${local_cycles} stop=${MARATHON_FLAP_STOP_SEC}s up=${MARATHON_FLAP_UP_SEC}s auth_wavers=per_minion" \
        || OVERALL_RC=1

    unset label fd_before rss_before local_cycles total_est fault_start fault_end fault_s i pid m
}

log "master_marathon scenario complete; results in ${RESULTS_FILE}"

exit "$OVERALL_RC"
