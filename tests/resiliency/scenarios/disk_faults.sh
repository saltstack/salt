#!/usr/bin/env bash
#
# Resiliency scenario: disk / filesystem faults on the master.
#
# Each phase exercises a different failure mode of the master's local
# filesystem state (cachedir, logdir, pki) and, after the fault clears,
# assert_reconnect verifies every minion in $MINION_IDS still answers
# test.ping within $RECONNECT_WINDOW_SEC and that fd/RSS haven't crept
# past the thresholds encoded in common.sh.
#
# Env contract: TOPOLOGY must be exported before running.  See
#   tests/resiliency/lib/common.sh
# for the topology -> container mapping.
#
# Phases (in order):
#   1. disk_cache_enospc     fill /var/cache/salt/master until ENOSPC
#                            (fallocate 500M preferred; dd until ENOSPC
#                            fallback).  Hold 60s, remove fill file,
#                            assert.
#   2. disk_cache_readonly   remount /var/cache/salt/master read-only
#                            (needs --privileged); chmod -w fallback if
#                            the cachedir isn't a mount point.  Hold 60s,
#                            restore, assert.
#   3. disk_cache_slow_io    write a 200M file with oflag=direct to
#                            pressure the buffer cache (proxy for slow
#                            I/O; no tc/stress-ng).  Assert.
#   4. disk_log_fill         fill /var/log/salt via dd; assert.
#   5. disk_pki_readonly     chmod -w /etc/salt/pki/master; 60s; restore;
#                            assert.  Exercises auth-cache reload path.
#
# Capabilities each phase needs (records setup_error if missing):
#   - all phases: ability to docker exec into $PRIMARY_MASTER as root.
#   - disk_cache_readonly: CAP_SYS_ADMIN inside the master container
#     (mount -o remount).  Falls back to chmod -w on failure.
#   - disk_cache_enospc / disk_log_fill: writable cachedir/logdir with
#     enough host-side space OR fallocate support so we don't actually
#     fill the host disk.
#
# Trap: on EXIT, every phase's cleanup is retried (rm fill files, unmount
# ro, chmod +w pki).  Safe to call multiple times.
#
# Don'ts:
#   - no /tmp scratch (use $SCENARIO_WORKDIR)
#   - no master restart (sibling scenario)
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
: "${DISK_FILL_MB:=500}"
: "${DISK_SLOW_MB:=200}"
export PHASE_DURATION_SEC DISK_FILL_MB DISK_SLOW_MB

SCENARIO_WORKDIR="${RESILIENCY_WORKDIR}/disk_faults"
mkdir -p "$SCENARIO_WORKDIR"

MASTER_CACHEDIR="/var/cache/salt/master"
MASTER_LOGDIR="/var/log/salt"
MASTER_PKIDIR="/etc/salt/pki/master"

# Track whether we've applied a fault whose teardown requires action on
# EXIT.  Each phase flips these on when it succeeds in applying its
# fault and off after a successful restore.
CACHE_FILL_ACTIVE=0
CACHE_RO_ACTIVE=0
CACHE_RO_MODE=""        # "mount" | "chmod"
CACHE_SLOW_ACTIVE=0
LOG_FILL_ACTIVE=0
PKI_RO_ACTIVE=0

CACHE_FILL_FILE="${MASTER_CACHEDIR}/__resiliency_fill"
CACHE_SLOW_FILE="${MASTER_CACHEDIR}/__resiliency_pressure"
LOG_FILL_FILE="${MASTER_LOGDIR}/__resiliency_fill"

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

# Remove a filler file we dropped inside the master container.  Safe to
# call on a file that no longer exists.
remove_master_file() {
    local path="$1"
    docker exec "$PRIMARY_MASTER" sh -c "rm -f '$path' 2>/dev/null || true" \
        >/dev/null 2>&1 || true
}

# Restore cachedir writability using whichever mode phase 2 used.
restore_cachedir() {
    case "$CACHE_RO_MODE" in
        mount)
            docker exec --privileged "$PRIMARY_MASTER" sh -c \
                "mount -o remount,rw '$MASTER_CACHEDIR' 2>/dev/null" \
                >/dev/null 2>&1 || true
            ;;
        chmod)
            docker exec "$PRIMARY_MASTER" sh -c \
                "chmod u+w '$MASTER_CACHEDIR' 2>/dev/null" \
                >/dev/null 2>&1 || true
            ;;
    esac
    CACHE_RO_ACTIVE=0
    CACHE_RO_MODE=""
}

# Restore PKI writability.
restore_pkidir() {
    docker exec "$PRIMARY_MASTER" sh -c \
        "chmod -R u+w '$MASTER_PKIDIR' 2>/dev/null" \
        >/dev/null 2>&1 || true
    PKI_RO_ACTIVE=0
}

on_exit() {
    local ec=$?
    [ "$CACHE_FILL_ACTIVE" = "1" ] && remove_master_file "$CACHE_FILL_FILE"
    [ "$CACHE_SLOW_ACTIVE" = "1" ] && remove_master_file "$CACHE_SLOW_FILE"
    [ "$LOG_FILL_ACTIVE" = "1" ] && remove_master_file "$LOG_FILL_FILE"
    [ "$CACHE_RO_ACTIVE" = "1" ] && restore_cachedir
    [ "$PKI_RO_ACTIVE" = "1" ] && restore_pkidir
    exit "$ec"
}
trap on_exit EXIT INT TERM

# -------------------------------------------------------------------------
# Phase 1: cachedir ENOSPC
# -------------------------------------------------------------------------
{
    label="disk_cache_enospc"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: filling ${MASTER_CACHEDIR} on ${PRIMARY_MASTER}"

    # Prefer fallocate (bounded, instant, exposes ENOSPC without actually
    # filling the host disk).  Fall back to dd-until-ENOSPC if fallocate
    # isn't present or returns a non-ENOSPC failure.
    applied=0
    fallocate_rc=1
    if docker exec "$PRIMARY_MASTER" sh -c 'command -v fallocate >/dev/null 2>&1'; then
        if docker exec "$PRIMARY_MASTER" sh -c \
            "fallocate -l ${DISK_FILL_MB}M '$CACHE_FILL_FILE' 2>/dev/null"; then
            fallocate_rc=0
            applied=1
            log "PHASE ${label}: fallocate ${DISK_FILL_MB}M succeeded"
        fi
    fi
    if [ "$applied" = "0" ]; then
        log "PHASE ${label}: fallocate unavailable/failed, falling back to dd"
        # dd will return non-zero when it hits ENOSPC; that's what we want.
        # Cap count so a pathologically large host disk doesn't actually
        # get filled -- 4096 * 1MB = 4GB headroom max.
        docker exec "$PRIMARY_MASTER" sh -c "
            dd if=/dev/zero of='$CACHE_FILL_FILE' bs=1M count=4096 2>/dev/null
        " >/dev/null 2>&1 || true
        # Did we manage to create a file at all?
        if docker exec "$PRIMARY_MASTER" sh -c "[ -s '$CACHE_FILL_FILE' ]" \
            >/dev/null 2>&1; then
            applied=1
            log "PHASE ${label}: dd fallback created fill file"
        fi
    fi

    if [ "$applied" = "0" ]; then
        log "PHASE ${label}: unable to allocate filler (no fallocate, dd produced empty file)"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "fallocate unavailable and dd produced empty file; may lack write perm or diskfull"
    else
        CACHE_FILL_ACTIVE=1
        sleep "$PHASE_DURATION_SEC"
        remove_master_file "$CACHE_FILL_FILE"
        CACHE_FILL_ACTIVE=0
        notes="method=fallocate size=${DISK_FILL_MB}M"
        [ "$fallocate_rc" != "0" ] && notes="method=dd-fallback"
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "$notes"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied fallocate_rc notes
}

# -------------------------------------------------------------------------
# Phase 2: cachedir read-only
# -------------------------------------------------------------------------
{
    label="disk_cache_readonly"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: making ${MASTER_CACHEDIR} read-only on ${PRIMARY_MASTER}"

    # Try bind-remount first.  If the cachedir isn't a mount point this
    # fails with "not a mount point" and we fall back to chmod -w.
    applied=0
    if docker exec --privileged "$PRIMARY_MASTER" sh -c \
        "mount -o remount,ro '$MASTER_CACHEDIR' 2>/dev/null" \
        >/dev/null 2>&1; then
        CACHE_RO_MODE="mount"
        applied=1
        log "PHASE ${label}: mount -o remount,ro succeeded"
    else
        # Try a self bind mount + remount ro so chmod-less setups still
        # get real read-only semantics.  This still needs CAP_SYS_ADMIN.
        if docker exec --privileged "$PRIMARY_MASTER" sh -c "
            mount --bind '$MASTER_CACHEDIR' '$MASTER_CACHEDIR' 2>/dev/null \
                && mount -o remount,ro,bind '$MASTER_CACHEDIR' 2>/dev/null
        " >/dev/null 2>&1; then
            CACHE_RO_MODE="mount"
            applied=1
            log "PHASE ${label}: self-bind + remount,ro succeeded"
        elif docker exec "$PRIMARY_MASTER" sh -c \
            "chmod u-w '$MASTER_CACHEDIR' 2>/dev/null" >/dev/null 2>&1; then
            CACHE_RO_MODE="chmod"
            applied=1
            log "PHASE ${label}: chmod u-w fallback applied"
        fi
    fi

    if [ "$applied" = "0" ]; then
        log "PHASE ${label}: neither mount -o remount,ro nor chmod -w worked"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "mount remount,ro failed (missing CAP_SYS_ADMIN?) and chmod fallback also failed"
    else
        CACHE_RO_ACTIVE=1
        sleep "$PHASE_DURATION_SEC"
        restore_cachedir
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "mode=${CACHE_RO_MODE:-unknown}"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied
}

# -------------------------------------------------------------------------
# Phase 3: slow-I/O proxy -- direct-io write to pressure the buffer cache
# -------------------------------------------------------------------------
{
    label="disk_cache_slow_io"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: pressuring buffer cache with ${DISK_SLOW_MB}M direct write"

    # Start the pressure write in the background so it's running during
    # the hold window; sync first to flush anything legit.  Capture the
    # container-side pid so cleanup can kill it if it overruns.
    applied=0
    if docker exec "$PRIMARY_MASTER" sh -c \
        "sync; dd if=/dev/zero of='$CACHE_SLOW_FILE' bs=1M count=${DISK_SLOW_MB} oflag=direct 2>/dev/null" \
        >/dev/null 2>&1; then
        applied=1
        CACHE_SLOW_ACTIVE=1
    else
        # Retry without oflag=direct (tmpfs/overlayfs reject direct io).
        if docker exec "$PRIMARY_MASTER" sh -c \
            "sync; dd if=/dev/zero of='$CACHE_SLOW_FILE' bs=1M count=${DISK_SLOW_MB} 2>/dev/null" \
            >/dev/null 2>&1; then
            applied=1
            CACHE_SLOW_ACTIVE=1
            log "PHASE ${label}: direct io unsupported, buffered write applied"
        fi
    fi

    if [ "$applied" = "0" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "unable to write pressure file; cachedir may be full or readonly"
    else
        sleep "$PHASE_DURATION_SEC"
        remove_master_file "$CACHE_SLOW_FILE"
        CACHE_SLOW_ACTIVE=0
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "dd ${DISK_SLOW_MB}M oflag=direct (or buffered fallback)"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied
}

# -------------------------------------------------------------------------
# Phase 4: /var/log/salt fill
# -------------------------------------------------------------------------
{
    label="disk_log_fill"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: filling ${MASTER_LOGDIR} on ${PRIMARY_MASTER}"

    applied=0
    if docker exec "$PRIMARY_MASTER" sh -c "[ -d '$MASTER_LOGDIR' ]" >/dev/null 2>&1; then
        if docker exec "$PRIMARY_MASTER" sh -c 'command -v fallocate >/dev/null 2>&1'; then
            if docker exec "$PRIMARY_MASTER" sh -c \
                "fallocate -l ${DISK_FILL_MB}M '$LOG_FILL_FILE' 2>/dev/null"; then
                applied=1
            fi
        fi
        if [ "$applied" = "0" ]; then
            docker exec "$PRIMARY_MASTER" sh -c "
                dd if=/dev/zero of='$LOG_FILL_FILE' bs=1M count=${DISK_FILL_MB} 2>/dev/null
            " >/dev/null 2>&1 || true
            if docker exec "$PRIMARY_MASTER" sh -c "[ -s '$LOG_FILL_FILE' ]" >/dev/null 2>&1; then
                applied=1
            fi
        fi
    else
        log "PHASE ${label}: ${MASTER_LOGDIR} does not exist on ${PRIMARY_MASTER}"
    fi

    if [ "$applied" = "0" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "could not create fill file in $MASTER_LOGDIR (missing dir or no write)"
    else
        LOG_FILL_ACTIVE=1
        sleep "$PHASE_DURATION_SEC"
        remove_master_file "$LOG_FILL_FILE"
        LOG_FILL_ACTIVE=0
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "fill ${DISK_FILL_MB}M in $MASTER_LOGDIR"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied
}

# -------------------------------------------------------------------------
# Phase 5: PKI read-only -- exercise auth-cache reload path
# -------------------------------------------------------------------------
{
    label="disk_pki_readonly"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: chmod -w on ${MASTER_PKIDIR}"

    applied=0
    if docker exec "$PRIMARY_MASTER" sh -c "[ -d '$MASTER_PKIDIR' ]" >/dev/null 2>&1; then
        if docker exec "$PRIMARY_MASTER" sh -c \
            "chmod -R u-w '$MASTER_PKIDIR' 2>/dev/null" >/dev/null 2>&1; then
            applied=1
            PKI_RO_ACTIVE=1
        fi
    else
        log "PHASE ${label}: ${MASTER_PKIDIR} not present on ${PRIMARY_MASTER}"
    fi

    if [ "$applied" = "0" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "chmod u-w failed on $MASTER_PKIDIR (missing dir or no perm)"
    else
        sleep "$PHASE_DURATION_SEC"
        restore_pkidir
        assert_reconnect "$label" "$PHASE_DURATION_SEC" "$fd_before" "$rss_before" \
            "chmod -R u-w $MASTER_PKIDIR"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied
}

log "disk_faults scenario complete; results in ${RESULTS_FILE}"

exit "$OVERALL_RC"
