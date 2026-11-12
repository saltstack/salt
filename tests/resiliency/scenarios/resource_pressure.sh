#!/usr/bin/env bash
#
# Resiliency scenario: resource pressure battery.
#
# Each phase squeezes a different resource on the primary master and then
# calls ``assert_reconnect`` to verify every minion in $MINION_IDS answers
# ``test.ping`` within $RECONNECT_WINDOW_SEC and that fd/rss haven't
# ballooned.
#
# Phases are independent: a failure in one does NOT skip the rest.  The
# script exits 0 only if every phase ran to "recovered"; otherwise 1.
#
# Phases:
#   1. resource_oom_squeeze    -- docker update --memory=200m for 90s, then 2g;
#                                 some workers may be OOM-killed, master must
#                                 respawn them.
#   2. resource_fd_squeeze     -- prlimit --nofile=256 on each salt-master pid
#                                 for 60s then relax. Needs util-linux; skipped
#                                 with setup_error if prlimit is missing.
#   3. resource_cpu_throttle   -- docker update --cpus=0.1 for 120s then restore.
#   4. resource_inode_exhaust  -- touch 100k files in /tmp then clean up.
#                                 If the filesystem won't allow it, records
#                                 setup_error.
#   5. resource_write_amplify  -- generate 10k log lines via logger(1); verify
#                                 no hang.  If logger is unavailable, falls
#                                 back to appending to /var/log/salt/stress.log
#                                 and records setup_error if neither works.
#
# Env knobs (with defaults):
#   OOM_HOLD_SEC          90    seconds to hold --memory=200m
#   OOM_RELAX_MEMORY      2g    memory to restore after the squeeze
#   FD_HOLD_SEC           60    seconds to hold prlimit --nofile=256
#   FD_RELAX_NOFILE       65536 nofile to restore after the squeeze
#   CPU_HOLD_SEC          120   seconds to hold --cpus=0.1
#   INODE_COUNT           100000 how many files to touch in /tmp
#   LOG_COUNT             10000 how many logger lines to emit
#   INTER_PHASE_WAIT_SEC  15    seconds between phases
#
# Exit code: 0 if every phase recovered, 1 otherwise (but every phase is
# still attempted).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${OOM_HOLD_SEC:=90}"
: "${OOM_RELAX_MEMORY:=2g}"
: "${FD_HOLD_SEC:=60}"
: "${FD_RELAX_NOFILE:=65536}"
: "${CPU_HOLD_SEC:=120}"
: "${INODE_COUNT:=100000}"
: "${LOG_COUNT:=10000}"
: "${INTER_PHASE_WAIT_SEC:=15}"

OVERALL_RC=0

# EXIT trap: always unwind any cgroup / fs constraint we may have applied.
# ``docker update --memory=0 --cpus=0`` is a no-op/relax on live containers
# (0 means "no limit") and is safe to run even if the phase succeeded.
cleanup() {
    docker update --memory=0 --memory-swap=-1 --cpus=0 "$PRIMARY_MASTER" >/dev/null 2>&1 || true
    docker exec "$PRIMARY_MASTER" sh -c "rm -f /tmp/inode-* /tmp/resiliency-inode.marker 2>/dev/null || true" >/dev/null 2>&1 || true
    log "resource_pressure: EXIT trap -- relaxed memory/cpu limits and cleaned /tmp scratch (best-effort)"
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
# Phase 1: memory squeeze -- OOM may kill workers; master must respawn.
# ---------------------------------------------------------------------------
phase_oom_squeeze() {
    local label="resource_oom_squeeze"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${OOM_HOLD_SEC}s mem=200m fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker update --memory=200m --memory-swap=200m "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "docker update --memory=200m ${PRIMARY_MASTER} failed"
        return 1
    fi
    sleep "$OOM_HOLD_SEC"
    if ! docker update --memory="$OOM_RELAX_MEMORY" --memory-swap=-1 "$PRIMARY_MASTER" >/dev/null 2>&1; then
        # Fall back to "no limit"; some engines reject explicit swap combos.
        docker update --memory=0 --memory-swap=-1 "$PRIMARY_MASTER" >/dev/null 2>&1 || true
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "mem=200m->${OOM_RELAX_MEMORY}"; then
        OVERALL_RC=1
    fi
}
phase_oom_squeeze
between_phases

# ---------------------------------------------------------------------------
# Phase 2: fd squeeze -- prlimit --nofile=256 on each salt-master pid.
# prlimit on PID 1 is a no-op in many containers; we iterate the actual
# salt-master pids.  Skipped with setup_error if prlimit isn't installed.
# ---------------------------------------------------------------------------
phase_fd_squeeze() {
    local label="resource_fd_squeeze"
    # Best-effort install of util-linux; if that fails we just skip.
    if ! docker exec "$PRIMARY_MASTER" sh -c "command -v prlimit >/dev/null 2>&1"; then
        docker exec "$PRIMARY_MASTER" sh -c "
            if command -v apt-get >/dev/null 2>&1; then
                apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq util-linux >/dev/null 2>&1
            elif command -v yum >/dev/null 2>&1; then
                yum install -y -q util-linux >/dev/null 2>&1
            elif command -v apk >/dev/null 2>&1; then
                apk add --no-cache util-linux >/dev/null 2>&1
            fi
        " >/dev/null 2>&1 || true
        if ! docker exec "$PRIMARY_MASTER" sh -c "command -v prlimit >/dev/null 2>&1"; then
            record_setup_error "$label" "prlimit not available in ${PRIMARY_MASTER}; util-linux install failed"
            return 0
        fi
    fi
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${FD_HOLD_SEC}s nofile=256 fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker exec "$PRIMARY_MASTER" sh -c '
        set -e
        pids=$(pgrep -f salt-master || true)
        if [ -z "$pids" ]; then
            echo "no salt-master pids" >&2
            exit 2
        fi
        for p in $pids; do
            prlimit --nofile=256 --pid=$p >/dev/null 2>&1 || true
        done
    ' >/dev/null 2>&1; then
        record_setup_error "$label" "prlimit --nofile=256 iteration failed in ${PRIMARY_MASTER}"
        return 1
    fi
    sleep "$FD_HOLD_SEC"
    # Relax to a generous nofile value so the master can breathe again.
    docker exec "$PRIMARY_MASTER" sh -c "
        for p in \$(pgrep -f salt-master || true); do
            prlimit --nofile=${FD_RELAX_NOFILE} --pid=\$p >/dev/null 2>&1 || true
        done
    " >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "nofile=256->${FD_RELAX_NOFILE}"; then
        OVERALL_RC=1
    fi
}
phase_fd_squeeze
between_phases

# ---------------------------------------------------------------------------
# Phase 3: CPU throttle -- 0.1 CPU for $CPU_HOLD_SEC, then restore.
# ---------------------------------------------------------------------------
phase_cpu_throttle() {
    local label="resource_cpu_throttle"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (hold=${CPU_HOLD_SEC}s cpus=0.1 fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    if ! docker update --cpus=0.1 "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_setup_error "$label" "docker update --cpus=0.1 ${PRIMARY_MASTER} failed"
        return 1
    fi
    sleep "$CPU_HOLD_SEC"
    docker update --cpus=0 "$PRIMARY_MASTER" >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "cpus=0.1->0"; then
        OVERALL_RC=1
    fi
}
phase_cpu_throttle
between_phases

# ---------------------------------------------------------------------------
# Phase 4: inode / /tmp exhaustion.  If the filesystem is a size-bounded
# tmpfs, we may fill it before hitting $INODE_COUNT; the ``|| true`` keeps
# the script moving.  Cleanup is unconditional.
# ---------------------------------------------------------------------------
phase_inode_exhaust() {
    local label="resource_inode_exhaust"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (count=${INODE_COUNT} fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    # Marker file so we can detect whether the squeeze ran at all.
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        : > /tmp/resiliency-inode.marker 2>/dev/null
    "; then
        record_setup_error "$label" "cannot write to /tmp inside ${PRIMARY_MASTER}"
        return 1
    fi
    docker exec "$PRIMARY_MASTER" sh -c "
        i=0
        while [ \$i -lt ${INODE_COUNT} ]; do
            touch /tmp/inode-\$i 2>/dev/null || break
            i=\$((i + 1))
        done
        echo \"touched=\$i\" >&2
    " >/dev/null 2>&1 || true
    local created
    created=$(docker exec "$PRIMARY_MASTER" sh -c "ls /tmp 2>/dev/null | grep -c '^inode-' || true" 2>/dev/null | tr -d '[:space:]')
    log "${label}: created ~${created:-0} /tmp files"
    # Unconditional cleanup -- rm -f with a glob can OOM, use find -delete.
    docker exec "$PRIMARY_MASTER" sh -c "
        find /tmp -maxdepth 1 -name 'inode-*' -delete 2>/dev/null || true
        rm -f /tmp/resiliency-inode.marker 2>/dev/null || true
    " >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "touched=${created:-0}"; then
        OVERALL_RC=1
    fi
}
phase_inode_exhaust
between_phases

# ---------------------------------------------------------------------------
# Phase 5: write amplification -- 10k logger lines.  Verify no hang.
# ---------------------------------------------------------------------------
phase_write_amplify() {
    local label="resource_write_amplify"
    local fd_before rss_before fault_start fault_end fault_s
    read -r fd_before rss_before < <(sample_all_minions)
    log "---- phase: ${label} (count=${LOG_COUNT} fd_before=${fd_before} rss_before_kb=${rss_before}) ----"
    fault_start=$(date +%s)
    # Prefer logger(1); fall back to appending to a file so the phase still
    # exercises write bandwidth even on minimal images.
    local used_logger=0
    if docker exec "$PRIMARY_MASTER" sh -c "command -v logger >/dev/null 2>&1"; then
        used_logger=1
        docker exec "$PRIMARY_MASTER" sh -c "
            i=0
            while [ \$i -lt ${LOG_COUNT} ]; do
                logger -t salt-stress 'x' 2>/dev/null || break
                i=\$((i + 1))
            done
        " >/dev/null 2>&1 || true
    else
        docker exec "$PRIMARY_MASTER" sh -c "
            mkdir -p /var/log/salt 2>/dev/null || true
            out=/var/log/salt/stress.log
            if ! : > \$out 2>/dev/null; then out=/tmp/stress.log; : > \$out; fi
            i=0
            while [ \$i -lt ${LOG_COUNT} ]; do
                echo \"salt-stress x \$i\" >> \$out
                i=\$((i + 1))
            done
        " >/dev/null 2>&1 || true
    fi
    fault_end=$(date +%s)
    fault_s=$(( fault_end - fault_start ))
    if [ "$used_logger" -eq 0 ]; then
        record_setup_error "$label" "logger(1) unavailable; used file-append fallback"
        # Still assert so we see whether the master survived the write burst.
    fi
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "logger=${used_logger} count=${LOG_COUNT}"; then
        OVERALL_RC=1
    fi
}
phase_write_amplify

log "resource_pressure battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
