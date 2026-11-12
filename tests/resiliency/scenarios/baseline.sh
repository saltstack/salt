#!/usr/bin/env bash
#
# Resiliency scenario: baseline sanity battery -- the "test of the test".
#
# None of the phases here inject a real fault.  Their purpose is to prove
# that the measurement harness (fd/RSS sampling, assert_reconnect's
# minute-normalised RSS-slope check, reconnect-window tightness) does NOT
# manufacture phantom leaks or phantom recoveries when the fleet is
# healthy.  If any of these phases flags a leak or a slow reconnect, the
# verdict from the fault scenarios is suspect: they're probably reporting
# the same noise.
#
# Phases (each independent; failures do not short-circuit the rest):
#
#   1. baseline_idle_300s                -- 5 min idle, no workload.  fd/rss
#                                           delta is the empirical no-leak
#                                           floor; logs loud but does NOT
#                                           fail if the floor is above 0.
#   2. baseline_idle_1800s               -- 30 min idle; only runs when
#                                           BASELINE_LONG_IDLE=1 (opt-in).
#                                           Otherwise records
#                                           outcome="setup_error" with
#                                           notes="BASELINE_LONG_IDLE=0".
#   3. baseline_workload_only_600s       -- KEY TEST.  Run the normal
#                                           workload (ping/grains/state/
#                                           manage.status loops) for 10 min
#                                           with NO fault injection.  Decide
#                                           pass/fail IN THIS SCRIPT using
#                                           the minute-normalised RSS slope
#                                           -- do not delegate to the
#                                           analyzer.  Then call
#                                           assert_reconnect to prove the
#                                           fleet is still healthy.
#   4. baseline_rapid_ping_burst_60s     -- 100 ms-interval test.ping burst
#                                           for 60s; assert every sweep
#                                           succeeded and no FD leak.
#   5. baseline_rapid_runner_60s         -- 100 ms-interval salt-run
#                                           manage.status burst for 60s.
#   6. baseline_ping_200_concurrent      -- 200 concurrent async pings via
#                                           xargs -P; everything must
#                                           settle within 2x the normal
#                                           reconnect window.
#   7. baseline_recovery_window_tightness-- "null fault": 1s SIGSTOP, assert
#                                           reconnect inside 10s (not 180s).
#                                           Catches an assert_reconnect that
#                                           rubber-stamps the full window
#                                           because it waits for the first
#                                           5s poll iteration.
#
# Guardrails:
#   - No phase leaves state that affects downstream phases.  The EXIT trap
#     only tears down the local workload process group and sends SIGCONT
#     to the primary master (belt-and-braces for the null-fault phase).
#   - baseline_idle_300s is TOLERANT: a non-zero fd delta is logged with
#     notes="fd grew +N; expected ~0; check monitoring stack footprint"
#     but still recorded as "recovered" so a noisy host doesn't poison the
#     whole suite.
#   - The workload loops are the ones from ../workload.sh; we launch our
#     own instance inside baseline_workload_only_600s because the
#     orchestrator's workload may already be running and we need a clean
#     start/stop around the measurement window.
#
# Env knobs (with defaults):
#   BASELINE_IDLE_SHORT_SEC      300  -- phase 1 hold
#   BASELINE_LONG_IDLE           0    -- set to 1 to enable phase 2
#   BASELINE_IDLE_LONG_SEC       1800 -- phase 2 hold
#   BASELINE_WORKLOAD_SEC        600  -- phase 3 workload hold
#   BASELINE_BURST_SEC           60   -- phase 4 + 5 burst duration
#   BASELINE_BURST_SLEEP_MS      100  -- inter-call sleep inside bursts
#   BASELINE_CONCURRENT_N        200  -- phase 6 concurrent pings
#   BASELINE_CONCURRENT_PAR      50   -- phase 6 xargs -P degree
#   BASELINE_TIGHT_HOLD_SEC      1    -- phase 7 SIGSTOP hold
#   BASELINE_TIGHT_WINDOW_SEC    10   -- phase 7 reconnect budget
#   INTER_PHASE_WAIT_SEC         15   -- seconds between phases
#
# Exit code: 0 if every phase recovered, 1 otherwise.  All phases are
# still attempted regardless of per-phase outcome.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${BASELINE_IDLE_SHORT_SEC:=$TIER_DEEPREC_SEC}"
: "${BASELINE_LONG_IDLE:=0}"
: "${BASELINE_IDLE_LONG_SEC:=$TIER_ACCUM_SEC}"
: "${BASELINE_WORKLOAD_SEC:=$TIER_BACKOFF_SEC}"
: "${BASELINE_BURST_SEC:=$TIER_STANDARD_SEC}"
: "${BASELINE_BURST_SLEEP_MS:=100}"
: "${BASELINE_CONCURRENT_N:=200}"
: "${BASELINE_CONCURRENT_PAR:=50}"
: "${BASELINE_TIGHT_HOLD_SEC:=1}"
: "${BASELINE_TIGHT_WINDOW_SEC:=10}"
: "${INTER_PHASE_WAIT_SEC:=$PACING_INTER_PHASE_SEC}"

OVERALL_RC=0

# Track the local workload pgid so the EXIT trap can tear it down even if
# we abort mid-phase (Ctrl-C, set -u trip).
LOCAL_WORKLOAD_PGID=""

cleanup() {
    if [ -n "$LOCAL_WORKLOAD_PGID" ]; then
        # Negative pid => signal the whole process group.
        kill -TERM "-${LOCAL_WORKLOAD_PGID}" >/dev/null 2>&1 || true
        # Give loops a moment to drain their in-flight docker exec calls.
        sleep 2
        kill -KILL "-${LOCAL_WORKLOAD_PGID}" >/dev/null 2>&1 || true
        LOCAL_WORKLOAD_PGID=""
    fi
    # Phase 7 leaves SIGSTOP for ~1s; make sure nothing is left stopped
    # if we bail mid-phase.
    for m in $MASTERS; do
        docker kill -s CONT "$m" >/dev/null 2>&1 || true
    done
    for c in $MINION_CONTAINERS; do
        docker kill -s CONT "$c" >/dev/null 2>&1 || true
    done
    log "baseline: EXIT trap -- cleanup complete"
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
# Phase 1: 5-minute idle baseline.
# No workload, no faults.  fd/rss delta is logged; if either grew we log
# loud but do NOT fail -- a healthy host still has non-zero deltas from
# monitoring agents (fd_exporter, prometheus scrapes).
# ---------------------------------------------------------------------------
phase_idle_300s() {
    local label="baseline_idle_300s"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (idle=${BASELINE_IDLE_SHORT_SEC}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    sleep "$BASELINE_IDLE_SHORT_SEC"
    local notes=""
    # Call assert_reconnect with fault_s=0; reconnect must be ~instant
    # because nothing was injected.  The RSS-slope check inside
    # assert_reconnect uses a 60-second floor on elapsed, so a flat fleet
    # still produces a well-defined slope.
    local fd_now rss_now
    read -r fd_now rss_now < <(sample_all_minions)
    local fd_delta=$((fd_now - fd_before))
    if [ "$fd_delta" -gt 0 ]; then
        notes="fd grew +${fd_delta}; expected ~0; check monitoring stack footprint"
        log "NOTE '${label}': ${notes}"
    fi
    if ! assert_reconnect "$label" "0" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 2: 30-minute idle baseline.  Opt-in -- costs 30 min of runner time.
# ---------------------------------------------------------------------------
phase_idle_1800s() {
    local label="baseline_idle_1800s"
    if [ "$BASELINE_LONG_IDLE" != "1" ]; then
        log "${label}: BASELINE_LONG_IDLE=${BASELINE_LONG_IDLE}, skipping (opt-in with BASELINE_LONG_IDLE=1)"
        record_result "$label" "skipped_for_topology" "-1" "0" "" "0" "0" "0" "BASELINE_LONG_IDLE=0"
        return 0
    fi
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (idle=${BASELINE_IDLE_LONG_SEC}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    sleep "$BASELINE_IDLE_LONG_SEC"
    if ! assert_reconnect "$label" "0" "$fd_before" "$rss_before" "long_idle=1"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 3: workload-only 600s.  THE KEY TEST.
#
# This phase computes the minute-normalised RSS slope IN-SCRIPT, not inside
# assert_reconnect's hidden calculation.  Rationale:
#
#   * We need a no-fault, workload-only slope to publish as the empirical
#     noise floor for the whole suite.  The analyzer reads this row and
#     uses it to decide whether a fault-phase leak is above-noise or not.
#   * By computing the slope here we can log the exact arithmetic, which
#     makes "why did baseline fail" a one-line answer in CI output
#     instead of a grep through assert_reconnect.
#
# Pass/fail criterion:
#
#     rss_kb_per_min = (rss_end - rss_start) * 60 / elapsed_seconds
#     pass iff rss_kb_per_min <= RSS_LEAK_KB_PER_MIN
#
# We record the row ourselves with the computed slope in notes, then also
# call assert_reconnect to prove minions are still answering.
# ---------------------------------------------------------------------------
phase_workload_only_600s() {
    local label="baseline_workload_only_600s"
    local workload="${SCRIPT_DIR}/../workload.sh"
    if [ ! -x "$workload" ]; then
        record_setup_error "$label" "workload script not executable: ${workload}"
        return 1
    fi
    local fd_before rss_before fd_end rss_end
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (workload=${BASELINE_WORKLOAD_SEC}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"

    # Launch workload in its own process group (setsid) so we can SIGTERM
    # the whole tree without racing the orchestrator's workload.
    setsid bash "$workload" >/dev/null 2>&1 &
    LOCAL_WORKLOAD_PGID=$!
    log "${label}: workload pgid=${LOCAL_WORKLOAD_PGID}"

    local start_ts end_ts elapsed
    start_ts=$(date +%s)
    sleep "$BASELINE_WORKLOAD_SEC"
    end_ts=$(date +%s)
    elapsed=$((end_ts - start_ts))

    # Tear down workload BEFORE sampling, so no in-flight exec affects
    # the minion RSS measurement.
    kill -TERM "-${LOCAL_WORKLOAD_PGID}" >/dev/null 2>&1 || true
    sleep 2
    kill -KILL "-${LOCAL_WORKLOAD_PGID}" >/dev/null 2>&1 || true
    LOCAL_WORKLOAD_PGID=""

    read -r fd_end rss_end < <(sample_all_minions)
    local fd_delta=$((fd_end - fd_before))
    local rss_delta=$((rss_end - rss_before))

    # Guard against elapsed=0; use the same 60s floor assert_reconnect
    # uses so our number is directly comparable.
    local window=$elapsed
    if [ "$window" -lt 60 ]; then window=60; fi
    local rss_per_min=$(( rss_delta * 60 / window ))

    local outcome="recovered"
    local phase_rc=0
    local notes="rss_kb_per_min=${rss_per_min} threshold=${RSS_LEAK_KB_PER_MIN} workload_s=${elapsed}"
    if [ "$rss_per_min" -gt "$RSS_LEAK_KB_PER_MIN" ]; then
        outcome="failed"
        phase_rc=1
        OVERALL_RC=1
        log "LEAK '${label}': ${notes}"
    else
        log "CLEAN '${label}': ${notes}"
    fi

    # Record our own verdict row with the slope embedded in notes.  The
    # analyzer treats this row as the empirical noise floor.
    record_result "$label" "$outcome" "0" "1" "" "$fd_delta" "$rss_delta" "$elapsed" "$notes"

    # Prove the fleet is still responsive.  Use a distinct label so the
    # row above (the slope verdict) isn't overwritten.
    local fd_ping rss_ping
    read -r fd_ping rss_ping < <(sample_all_minions)
    if ! assert_reconnect "${label}_ping" "0" "$fd_ping" "$rss_ping" "post_workload_health_check"; then
        OVERALL_RC=1
        phase_rc=1
    fi
    return "$phase_rc"
}

# ---------------------------------------------------------------------------
# Phase 4: rapid test.ping burst for 60s at 100ms interval.
# Counts successful vs failed sweeps; asserts 100% success.
# ---------------------------------------------------------------------------
phase_rapid_ping_burst_60s() {
    local label="baseline_rapid_ping_burst_60s"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (duration=${BASELINE_BURST_SEC}s sleep_ms=${BASELINE_BURST_SLEEP_MS} fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    local sleep_frac
    # Convert milliseconds to a float suitable for `sleep`.
    sleep_frac=$(python3 -c "print('%.3f' % (${BASELINE_BURST_SLEEP_MS}/1000.0))")
    local deadline=$(( $(date +%s) + BASELINE_BURST_SEC ))
    local attempts=0 failures=0
    while [ "$(date +%s)" -lt "$deadline" ]; do
        attempts=$((attempts + 1))
        if ! docker exec "$PRIMARY_MASTER" salt --timeout=10 --out=json '*' test.ping >/dev/null 2>&1; then
            failures=$((failures + 1))
        fi
        sleep "$sleep_frac"
    done
    local fd_end rss_end
    read -r fd_end rss_end < <(sample_all_minions)
    local fd_delta=$((fd_end - fd_before))
    local rss_delta=$((rss_end - rss_before))
    local notes="attempts=${attempts} failures=${failures}"
    if [ "$failures" -gt 0 ] || [ "$fd_delta" -gt 0 ]; then
        log "FAILED '${label}': ${notes} fd_delta=${fd_delta} rss_delta_kb=${rss_delta}"
        record_result "$label" "failed" "-1" "$attempts" "" "$fd_delta" "$rss_delta" "$BASELINE_BURST_SEC" "$notes"
        OVERALL_RC=1
        return 1
    fi
    log "CLEAN '${label}': ${notes} fd_delta=${fd_delta} rss_delta_kb=${rss_delta}"
    record_result "$label" "recovered" "0" "$attempts" "" "$fd_delta" "$rss_delta" "$BASELINE_BURST_SEC" "$notes"
    return 0
}

# ---------------------------------------------------------------------------
# Phase 5: rapid salt-run manage.status burst.
# ---------------------------------------------------------------------------
phase_rapid_runner_60s() {
    local label="baseline_rapid_runner_60s"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (duration=${BASELINE_BURST_SEC}s sleep_ms=${BASELINE_BURST_SLEEP_MS} fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    local sleep_frac
    sleep_frac=$(python3 -c "print('%.3f' % (${BASELINE_BURST_SLEEP_MS}/1000.0))")
    local deadline=$(( $(date +%s) + BASELINE_BURST_SEC ))
    local attempts=0 failures=0
    while [ "$(date +%s)" -lt "$deadline" ]; do
        attempts=$((attempts + 1))
        if ! docker exec "$PRIMARY_MASTER" salt-run manage.status >/dev/null 2>&1; then
            failures=$((failures + 1))
        fi
        sleep "$sleep_frac"
    done
    local fd_end rss_end
    read -r fd_end rss_end < <(sample_all_minions)
    local fd_delta=$((fd_end - fd_before))
    local rss_delta=$((rss_end - rss_before))
    local notes="attempts=${attempts} failures=${failures}"
    if [ "$failures" -gt 0 ] || [ "$fd_delta" -gt 0 ]; then
        log "FAILED '${label}': ${notes} fd_delta=${fd_delta} rss_delta_kb=${rss_delta}"
        record_result "$label" "failed" "-1" "$attempts" "" "$fd_delta" "$rss_delta" "$BASELINE_BURST_SEC" "$notes"
        OVERALL_RC=1
        return 1
    fi
    log "CLEAN '${label}': ${notes} fd_delta=${fd_delta} rss_delta_kb=${rss_delta}"
    record_result "$label" "recovered" "0" "$attempts" "" "$fd_delta" "$rss_delta" "$BASELINE_BURST_SEC" "$notes"
    return 0
}

# ---------------------------------------------------------------------------
# Phase 6: 200 concurrent async pings via xargs -P.
# Everything must settle (fleet responsive via assert_reconnect) within
# 2x the normal reconnect window.
# ---------------------------------------------------------------------------
phase_ping_200_concurrent() {
    local label="baseline_ping_200_concurrent"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (n=${BASELINE_CONCURRENT_N} par=${BASELINE_CONCURRENT_PAR} fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    local fault_start fault_end fault_s
    fault_start=$(date +%s)
    # Fire N async pings; xargs -P controls the concurrency fan-out.
    # Any individual failure is tolerated here -- we rely on
    # assert_reconnect to decide health.
    seq 1 "$BASELINE_CONCURRENT_N" | xargs -I {} -P "$BASELINE_CONCURRENT_PAR" \
        docker exec "$PRIMARY_MASTER" salt --async '*' test.ping \
        >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))

    # Temporarily widen the window to 2x normal for just this assertion.
    local saved_window="$RECONNECT_WINDOW_SEC"
    RECONNECT_WINDOW_SEC=$(( saved_window * 2 ))
    export RECONNECT_WINDOW_SEC
    local notes="n=${BASELINE_CONCURRENT_N} par=${BASELINE_CONCURRENT_PAR} window=${RECONNECT_WINDOW_SEC}s"
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
    RECONNECT_WINDOW_SEC="$saved_window"
    export RECONNECT_WINDOW_SEC
}

# ---------------------------------------------------------------------------
# Phase 7: null-fault recovery-window tightness.
# Inject a 1-second SIGSTOP on the primary master -- not long enough to
# break anything -- and assert the fleet is back within 10 seconds.  If
# assert_reconnect ever rubber-stamps the max window (180s) this phase
# catches it.
# ---------------------------------------------------------------------------
phase_recovery_window_tightness() {
    local label="baseline_recovery_window_tightness"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${BASELINE_TIGHT_HOLD_SEC}s budget=${BASELINE_TIGHT_WINDOW_SEC}s fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    local fault_start fault_end fault_s
    fault_start=$(date +%s)
    if ! docker kill -s STOP "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "docker kill -s STOP ${PRIMARY_MASTER} failed"
        return 1
    fi
    sleep "$BASELINE_TIGHT_HOLD_SEC"
    if ! docker kill -s CONT "$PRIMARY_MASTER" >/dev/null 2>&1; then
        # Try harder; a stuck SIGSTOP leaves the fleet in a bad state.
        docker kill -s CONT "$PRIMARY_MASTER" >/dev/null 2>&1 || true
        record_setup_error "$label" "docker kill -s CONT ${PRIMARY_MASTER} failed"
        return 1
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))

    # Tighten the window for just this assertion.
    local saved_window="$RECONNECT_WINDOW_SEC"
    RECONNECT_WINDOW_SEC="$BASELINE_TIGHT_WINDOW_SEC"
    export RECONNECT_WINDOW_SEC
    local notes="null_fault hold=${BASELINE_TIGHT_HOLD_SEC}s budget=${BASELINE_TIGHT_WINDOW_SEC}s"
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
    RECONNECT_WINDOW_SEC="$saved_window"
    export RECONNECT_WINDOW_SEC
}

# ---------------------------------------------------------------------------
# Drive the battery.
# ---------------------------------------------------------------------------
phase_idle_300s
between_phases
phase_idle_1800s
between_phases
phase_workload_only_600s
between_phases
phase_rapid_ping_burst_60s
between_phases
phase_rapid_runner_60s
between_phases
phase_ping_200_concurrent
between_phases
phase_recovery_window_tightness

log "baseline battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
