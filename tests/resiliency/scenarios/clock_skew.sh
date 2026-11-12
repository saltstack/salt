#!/usr/bin/env bash
#
# Resiliency scenario: clock-skew faults.
#
# Walks minion and master containers through forward / backward clock
# jumps (small and large) and a mid-auth skew race.  After each phase
# the clock is restored and assert_reconnect verifies every minion in
# $MINION_IDS still answers test.ping within $RECONNECT_WINDOW_SEC and
# that fd/RSS haven't crept past the thresholds encoded in common.sh.
#
# Env contract: TOPOLOGY must be exported before running.  See
#   tests/resiliency/lib/common.sh
# for the topology -> container mapping.
#
# Phases (in order):
#   1. clock_minion_fwd_60s       first MINION_CONTAINERS: date -s '+60s'
#   2. clock_minion_back_300s     first MINION_CONTAINERS: date -s '-5m'
#   3. clock_master_fwd_60s       PRIMARY_MASTER: date -s '+60s'
#   4. clock_master_back_3600s    PRIMARY_MASTER: date -s '-1h'
#                                 (tests mWorker monotonic-vs-wall key
#                                 rotation handling)
#   5. clock_drift_during_auth    set minion clock +120s while the
#                                 minion container is mid-restart
#
# Capabilities each phase needs (records setup_error if missing):
#   - phases 1-4: CAP_SYS_TIME inside the target container so `date -s`
#     actually changes the kernel clock.  If the container shares the
#     host clock (typical for docker without CAP_SYS_TIME), date -s
#     fails or silently no-ops; we detect that by re-reading the clock
#     and recording setup_error with notes="date -s failed; container
#     lacks CAP_SYS_TIME".  `faketime` is tried as a fallback if
#     installed in the container, but faketime only shifts the view
#     for a newly-spawned process so it can't retrofit a running
#     salt-minion/salt-master -- it's documented as limited here.
#   - phase 5: timing-sensitive; the skew needs to land after dockerd
#     starts the container but before salt-minion completes auth.  If
#     the race window is too tight we record setup_error with notes.
#
# Trap: on EXIT, every phase's cleanup is retried (restore clock via
# hwclock -s or an absolute date -s back to current host UTC).
#
# Don'ts:
#   - no /tmp scratch (use $SCENARIO_WORKDIR)
#   - no committing

set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${HERE}/../lib/common.sh"

load_topology

# Scenario-local exit code: 0 = all phases recovered, 1 = at least one phase
# failed (recovery missed OR leak threshold exceeded).  Final line of this
# file is ``exit "$OVERALL_RC"`` so the orchestrator sees the aggregate.
OVERALL_RC=0

: "${PHASE_DURATION_SEC:=$TIER_STANDARD_SEC}"
export PHASE_DURATION_SEC

SCENARIO_WORKDIR="${RESILIENCY_WORKDIR}/clock_skew"
mkdir -p "$SCENARIO_WORKDIR"

# Track which containers we've skewed so the trap can restore them.
SKEWED_CONTAINERS=""

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

# First element of $MINION_CONTAINERS -- phases 1,2,5 target just one.
first_minion() {
    printf '%s\n' "$MINION_CONTAINERS" | awk '{print $1}'
}

# Read the current UTC epoch inside the container.  Empty on error.
container_epoch() {
    docker exec "$1" sh -c 'date -u +%s' 2>/dev/null | tr -d '[:space:]'
}

# Check whether `date -s` actually moves the clock in $1.  Sets the clock
# forward by 5 seconds, re-reads, then restores to the host-UTC epoch.
# Returns 0 if the skew took effect, 1 otherwise.  On failure the clock
# is left at (or very close to) host UTC.
can_set_clock() {
    local c="$1"
    local before host_now after
    before="$(container_epoch "$c")"
    [ -z "$before" ] && return 1
    host_now="$(date -u +%s)"
    if ! docker exec "$c" sh -c "date -u -s '@$(( host_now + 5 ))' >/dev/null 2>&1"; then
        return 1
    fi
    after="$(container_epoch "$c")"
    # Restore to host UTC regardless of whether the probe worked.
    docker exec "$c" sh -c "date -u -s '@$(date -u +%s)' >/dev/null 2>&1" || true
    [ -z "$after" ] && return 1
    # Accept any forward movement >= 3s; containers that reject date -s
    # usually leave `after` identical to `before` (shared host clock).
    [ "$after" -ge $(( before + 3 )) ]
}

# Apply a relative skew to a container.  $1=container, $2=seconds (signed).
# Returns 0 on success.
apply_skew() {
    local c="$1" delta="$2"
    local target
    target=$(( $(date -u +%s) + delta ))
    if docker exec "$c" sh -c "date -u -s '@${target}' >/dev/null 2>&1"; then
        case " $SKEWED_CONTAINERS " in
            *" $c "*) : ;;
            *) SKEWED_CONTAINERS="$SKEWED_CONTAINERS $c" ;;
        esac
        return 0
    fi
    return 1
}

# Restore a container's clock to host UTC.  Prefers `hwclock -s` (reads
# the host RTC via /dev/rtc if the container was granted access) and
# falls back to an absolute date -s of host UTC.
restore_clock() {
    local c="$1"
    # hwclock will silently no-op in most containers; keep it cheap.
    docker exec "$c" sh -c 'hwclock -s 2>/dev/null' >/dev/null 2>&1 || true
    docker exec "$c" sh -c "date -u -s '@$(date -u +%s)' >/dev/null 2>&1" || true
}

on_exit() {
    local ec=$?
    local c
    for c in $SKEWED_CONTAINERS; do
        restore_clock "$c" || true
    done
    SKEWED_CONTAINERS=""
    exit "$ec"
}
trap on_exit EXIT INT TERM

# -------------------------------------------------------------------------
# Phase runner.  Handles probe -> sample -> apply -> hold -> restore ->
# assert.  Takes label, container, and signed delta seconds.  Records
# setup_error if CAP_SYS_TIME is missing.
# -------------------------------------------------------------------------
run_clock_phase() {
    local label="$1" container="$2" delta="$3"
    local fd_before rss_before
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: skew $container by ${delta}s for ${PHASE_DURATION_SEC}s"

    if ! can_set_clock "$container"; then
        log "PHASE ${label}: date -s probe failed on $container"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "date -s failed; container lacks CAP_SYS_TIME"
        return 0
    fi

    if ! apply_skew "$container" "$delta"; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "apply_skew failed after probe succeeded (race?)"
        return 0
    fi

    sleep "$PHASE_DURATION_SEC"
    restore_clock "$container"
    # Drop from SKEWED_CONTAINERS now that it's restored; the trap is a
    # safety net for mid-phase death only.
    SKEWED_CONTAINERS="$(printf '%s\n' $SKEWED_CONTAINERS | grep -v "^${container}$" | tr '\n' ' ')"

    assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
        "skew ${delta}s on $container"  || OVERALL_RC=1
}

# -------------------------------------------------------------------------
# Main battery
# -------------------------------------------------------------------------
log "clock_skew scenario starting topology=${TOPOLOGY} primary=${PRIMARY_MASTER}"
FIRST_MINION="$(first_minion)"
log "clock_skew: minion target=${FIRST_MINION}"

# Phase 1: minion +60s
run_clock_phase "clock_minion_fwd_60s" "$FIRST_MINION" 60

# Phase 2: minion -300s
run_clock_phase "clock_minion_back_300s" "$FIRST_MINION" -300

# Phase 3: master +60s
run_clock_phase "clock_master_fwd_60s" "$PRIMARY_MASTER" 60

# Phase 4: master -3600s (tests mWorker key-rotation monotonic handling)
run_clock_phase "clock_master_back_3600s" "$PRIMARY_MASTER" -3600

# -------------------------------------------------------------------------
# Phase 5: clock drift during auth
#
# Restart the first minion container AND skew its clock +120s before
# salt-minion finishes authing to the master.  There is no public
# "authenticated" hook we can race against, so we approximate: fire
# `docker restart` async, poll for `docker inspect .State.Running=true`
# (usually a few hundred ms), and immediately apply the skew.  If the
# container doesn't honour date -s (CAP_SYS_TIME missing) we record
# setup_error.  If the race window is too tight to be meaningful we
# flag that in notes.
# -------------------------------------------------------------------------
{
    label="clock_drift_during_auth"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: restart ${FIRST_MINION} and skew +120s mid-auth"

    # Probe once so we can distinguish "race missed" from "no CAP_SYS_TIME".
    if ! can_set_clock "$FIRST_MINION"; then
        log "PHASE ${label}: date -s probe failed on $FIRST_MINION"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "date -s failed; container lacks CAP_SYS_TIME"
    else
        # Kick off the restart in the background.  docker restart blocks
        # until the container is back up; we need to inject the skew
        # while it's starting, so we race against `docker inspect`.
        docker restart --time 2 "$FIRST_MINION" >/dev/null 2>&1 &
        restart_pid=$!

        # Wait for the container to come back to Running=true.  dockerd
        # transitions through "restarting" so we spin on State.Running.
        skew_applied=0
        race_notes=""
        deadline=$(( $(date +%s) + 30 ))
        while [ "$(date +%s)" -lt "$deadline" ]; do
            state="$(docker inspect -f '{{.State.Running}}' "$FIRST_MINION" 2>/dev/null)"
            if [ "$state" = "true" ]; then
                # Container is up; attempt the skew *now*.
                if apply_skew "$FIRST_MINION" 120; then
                    skew_applied=1
                fi
                break
            fi
            # Tight loop; sub-second resolution matters for the race.
            sleep 0.1 2>/dev/null || sleep 1
        done

        wait "$restart_pid" 2>/dev/null || true

        if [ "$skew_applied" = "0" ]; then
            race_notes="unable to apply skew within 30s of restart; race may be impractical on this host"
            log "PHASE ${label}: ${race_notes}"
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" "$race_notes"
        else
            # Hold the skew long enough to cover salt-minion's first-auth
            # retry window (minion.auth_tries defaults mean ~2-3 attempts
            # within 60s with the default auth_timeout).
            sleep "$PHASE_DURATION_SEC"
            restore_clock "$FIRST_MINION"
            SKEWED_CONTAINERS="$(printf '%s\n' $SKEWED_CONTAINERS | grep -v "^${FIRST_MINION}$" | tr '\n' ' ')"
            assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
                "skew +120s applied during post-restart auth window"  || OVERALL_RC=1
        fi
    fi
    unset label fd_before rss_before restart_pid skew_applied race_notes deadline state
}

log "clock_skew scenario complete; results in ${RESULTS_FILE}"

exit "$OVERALL_RC"
