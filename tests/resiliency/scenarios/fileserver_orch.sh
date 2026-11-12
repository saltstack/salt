#!/usr/bin/env bash
#
# Resiliency scenario: fileserver + orchestration-adjacent faults.
#
# Exercises the master's file-serving / pillar / fileserver-cache paths
# and orchestration-adjacent "whole-plumbing" faults (docker network
# disconnect, bridge iface down, process-manager subprocess kill,
# minion-record cache wipe).  After every phase the fault is cleared
# and assert_reconnect verifies every minion in $MINION_IDS still
# answers test.ping within $RECONNECT_WINDOW_SEC and fd/rss haven't
# crept past the thresholds encoded in common.sh.
#
# Env contract: TOPOLOGY must be exported before running.  See
#   tests/resiliency/lib/common.sh
# for the topology -> container mapping.
#
# Phases (in order):
#   1. fs_sls_swap_mid_state           kick off a state.apply --async,
#                                      mutate a referenced SLS on-disk
#                                      mid-run; hash change should force
#                                      fileserver refresh.  Assert.
#   2. fs_large_file_mid_cache         kick off cp.cache_file on a 50M
#                                      file; delete + recreate source
#                                      mid-fetch.  Assert.
#   3. fs_pillar_flip_mid_run          sed-rewrite pillar top.sls during
#                                      a pillar-consuming state; restore;
#                                      assert.
#   4. fs_master_srv_remount           mount -o remount,ro /srv/salt on
#                                      the master (needs CAP_SYS_ADMIN);
#                                      30s; remount,rw; assert.
#   5. orch_docker_network_disconnect  docker network disconnect
#                                      $PRIMARY_MASTER; 60s; reconnect;
#                                      assert.
#   6. orch_docker_network_disconnect_minion
#                                      same on first minion container.
#   7. orch_volume_remount_simulate    rm -rf + recreate
#                                      /var/cache/salt/master/minions on
#                                      the master; master should
#                                      regenerate minion records.
#                                      Assert.
#   8. orch_restart_docker_bridge_iface_down
#                                      ip link set $CHOKE_IFACE down on
#                                      $CHOKE_CONTAINER (needs
#                                      CAP_NET_ADMIN); 30s; up; assert.
#   9. orch_random_kill_one_process_tree
#                                      pick a random non-MainProcess
#                                      master subprocess, SIGKILL,
#                                      ProcessManager should respawn.
#                                      Assert.
#
# Skips / setup_error cases:
#   - fs_sls_swap_mid_state / fs_large_file_mid_cache on TOPOLOGY=single:
#     /srv/salt is bind-mounted read-only in the single compose, so SLS
#     edits are impossible without a bind-remount; recorded as
#     setup_error when the write probe fails.
#   - fs_pillar_flip_mid_run: single topology has no pillar_roots
#     configured; skipped when pillar top.sls isn't present on master.
#   - fs_master_srv_remount: needs CAP_SYS_ADMIN inside the master
#     container.  On single, /srv/salt is already ro so this phase
#     becomes a no-op and is recorded as setup_error.
#   - orch_restart_docker_bridge_iface_down: needs CAP_NET_ADMIN inside
#     $CHOKE_CONTAINER AND `ip` must be present.  Records setup_error
#     if either condition fails rather than hanging the suite.
#   - orch_random_kill_one_process_tree: if the master only exposes a
#     single process (MainProcess) at exec time, phase is a no-op and
#     records setup_error.
#
# Trap: on EXIT every phase's teardown is retried --
#   - detached docker networks are reconnected
#   - ro-remounted /srv/salt is remounted rw
#   - downed interfaces are brought back up
#   - deleted cache dirs are recreated as empty dirs (safe; master
#     regenerates on next auth / job return)
# Safe to call multiple times.
#
# Don'ts:
#   - no master restart (sibling scenario)
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

: "${PHASE_DURATION_SEC:=60}"
: "${SHORT_FAULT_SEC:=30}"
: "${LARGE_FILE_MB:=50}"
export PHASE_DURATION_SEC SHORT_FAULT_SEC LARGE_FILE_MB

SCENARIO_WORKDIR="${RESILIENCY_WORKDIR}/fileserver_orch"
mkdir -p "$SCENARIO_WORKDIR"

# Docker-compose project network name (topology-dependent).  See
# feedback_merge_forward_per_file_prompt / common.sh: COMPOSE_PROJECT
# differs per topology.  Resolve once, fall back to introspection via
# docker inspect if the convention-based name doesn't exist.
SALT_NET="${COMPOSE_PROJECT}_salt-net"
if ! docker network inspect "$SALT_NET" >/dev/null 2>&1; then
    detected=$(docker inspect "$PRIMARY_MASTER" --format \
        '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
        | awk '{print $1}')
    if [ -n "$detected" ]; then
        log "resolved network via introspection: '$detected' (fallback for '$SALT_NET')"
        SALT_NET="$detected"
    fi
fi
export SALT_NET

# Trap-state flags.  Each phase flips its flag on when it applies its
# fault and off after successful restore.  on_exit retries every
# still-active restore.
SRV_SALT_RO_ACTIVE=0
MASTER_NET_DETACHED=0
MINION_NET_DETACHED=0
MINION_NET_CONTAINER=""
BRIDGE_IFACE_DOWN_ACTIVE=0
BRIDGE_IFACE_DOWN_CONTAINER=""
BRIDGE_IFACE_DOWN_IFACE=""
MINION_RECORDS_WIPED=0
PILLAR_TOP_BACKUP=""

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

# Does the master have a writable /srv/salt mount?  Returns 0 if we can
# create a dotfile there, 1 otherwise.  We don't leave the probe behind.
master_srv_salt_writable() {
    docker exec "$PRIMARY_MASTER" sh -c \
        '( touch /srv/salt/.__resiliency_probe && rm -f /srv/salt/.__resiliency_probe ) >/dev/null 2>&1'
}

# Locate the first state SLS under /srv/salt we can safely append a
# whitespace-only line to.  Prefer webserver.sls (seen in all three
# monitoring stacks); fall back to the first *.sls at /srv/salt depth 1.
pick_mutable_sls() {
    local candidate
    for candidate in /srv/salt/webserver.sls /srv/salt/top.sls; do
        if docker exec "$PRIMARY_MASTER" sh -c "[ -f '$candidate' ]" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    docker exec "$PRIMARY_MASTER" sh -c \
        "find /srv/salt -maxdepth 2 -name '*.sls' -type f 2>/dev/null | head -1" \
        | tr -d '[:space:]'
}

# Locate pillar top.sls on the master.  Prints path or empty string.
pick_pillar_top() {
    local candidate
    for candidate in /srv/salt/pillar/base/top.sls /srv/pillar/top.sls; do
        if docker exec "$PRIMARY_MASTER" sh -c "[ -f '$candidate' ]" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    printf '\n'
}

# Restore a remount,rw on /srv/salt.  Safe to call when nothing was
# remounted (mount -o remount,rw will just reaffirm current state).
restore_srv_salt_rw() {
    docker exec --privileged "$PRIMARY_MASTER" sh -c \
        "mount -o remount,rw /srv/salt 2>/dev/null" >/dev/null 2>&1 || true
    SRV_SALT_RO_ACTIVE=0
}

# Reconnect a container to $SALT_NET.  Idempotent (returns 0 even if
# already connected).
reconnect_to_net() {
    local container="$1"
    docker network connect "$SALT_NET" "$container" >/dev/null 2>&1 || true
}

restore_bridge_iface() {
    [ -z "$BRIDGE_IFACE_DOWN_CONTAINER" ] && return 0
    docker exec --privileged "$BRIDGE_IFACE_DOWN_CONTAINER" sh -c \
        "ip link set $BRIDGE_IFACE_DOWN_IFACE up 2>/dev/null" >/dev/null 2>&1 || true
    BRIDGE_IFACE_DOWN_ACTIVE=0
}

restore_pillar_top() {
    [ -z "$PILLAR_TOP_BACKUP" ] && return 0
    docker exec "$PRIMARY_MASTER" sh -c \
        "[ -f '$PILLAR_TOP_BACKUP' ] && cp -f '$PILLAR_TOP_BACKUP' '${PILLAR_TOP_BACKUP%.bak}' && rm -f '$PILLAR_TOP_BACKUP'" \
        >/dev/null 2>&1 || true
    PILLAR_TOP_BACKUP=""
}

restore_minion_records_dir() {
    docker exec "$PRIMARY_MASTER" sh -c \
        "mkdir -p /var/cache/salt/master/minions 2>/dev/null" \
        >/dev/null 2>&1 || true
    MINION_RECORDS_WIPED=0
}

on_exit() {
    local ec=$?
    [ "$SRV_SALT_RO_ACTIVE" = "1" ] && restore_srv_salt_rw
    [ "$MASTER_NET_DETACHED" = "1" ] && reconnect_to_net "$PRIMARY_MASTER" \
        && MASTER_NET_DETACHED=0
    if [ "$MINION_NET_DETACHED" = "1" ] && [ -n "$MINION_NET_CONTAINER" ]; then
        reconnect_to_net "$MINION_NET_CONTAINER"
        MINION_NET_DETACHED=0
    fi
    [ "$BRIDGE_IFACE_DOWN_ACTIVE" = "1" ] && restore_bridge_iface
    [ -n "$PILLAR_TOP_BACKUP" ] && restore_pillar_top
    [ "$MINION_RECORDS_WIPED" = "1" ] && restore_minion_records_dir
    exit "$ec"
}
trap on_exit EXIT INT TERM

# -------------------------------------------------------------------------
# Phase 1: SLS swap mid-state
# -------------------------------------------------------------------------
{
    label="fs_sls_swap_mid_state"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: kicking off state.apply --async then mutating SLS"

    if ! master_srv_salt_writable; then
        log "PHASE ${label}: /srv/salt is read-only on ${PRIMARY_MASTER}, skipping"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "/srv/salt mount is read-only on master; cannot mutate SLS in place"
    else
        target_sls="$(pick_mutable_sls)"
        if [ -z "$target_sls" ]; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "no SLS under /srv/salt to mutate"
        else
            fault_start=$(date +%s)
            # Fire the state async so we can mutate during the run.  We
            # intentionally don't collect job id -- we only care that
            # minions survive the swap and re-answer test.ping.
            docker exec -d "$PRIMARY_MASTER" sh -c \
                "salt --async '*' state.apply heavy >/dev/null 2>&1 || salt --async '*' state.apply webserver >/dev/null 2>&1" \
                >/dev/null 2>&1 || true
            sleep 5
            # Append a newline to force a hash change; prepend a timestamp
            # comment so the mutation is visible in post-mortem logs.
            docker exec "$PRIMARY_MASTER" sh -c \
                "printf '# resiliency-swap %s\n' \"\$(date -u +%s)\" >> '$target_sls'" \
                >/dev/null 2>&1 || true
            sleep "$SHORT_FAULT_SEC"
            fault_end=$(date +%s)
            fault_s=$((fault_end - fault_start))
            assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
                "swapped=$target_sls"  || OVERALL_RC=1
        fi
    fi
    unset label fd_before rss_before target_sls fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 2: cp.cache_file interrupted by source delete+recreate
# -------------------------------------------------------------------------
{
    label="fs_large_file_mid_cache"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: cp.cache_file of ${LARGE_FILE_MB}M file, delete+recreate mid-fetch"

    if ! master_srv_salt_writable; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "/srv/salt mount is read-only on master; cannot place large source file"
    else
        large_file_path="/srv/salt/__resiliency_large.bin"
        large_file_salt="salt://__resiliency_large.bin"
        # Prefer fallocate for an instant sparse file; fall back to dd.
        if docker exec "$PRIMARY_MASTER" sh -c 'command -v fallocate >/dev/null 2>&1'; then
            docker exec "$PRIMARY_MASTER" sh -c \
                "fallocate -l ${LARGE_FILE_MB}M '$large_file_path' 2>/dev/null" \
                >/dev/null 2>&1 || true
        fi
        if ! docker exec "$PRIMARY_MASTER" sh -c "[ -s '$large_file_path' ]" >/dev/null 2>&1; then
            docker exec "$PRIMARY_MASTER" sh -c \
                "dd if=/dev/zero of='$large_file_path' bs=1M count=${LARGE_FILE_MB} 2>/dev/null" \
                >/dev/null 2>&1 || true
        fi
        if ! docker exec "$PRIMARY_MASTER" sh -c "[ -s '$large_file_path' ]" >/dev/null 2>&1; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "failed to create large source file $large_file_path"
        else
            fault_start=$(date +%s)
            # Kick cache fetch on every minion in the background from the
            # master CLI (async).  We don't wait -- the mutation timing is
            # what we care about.
            docker exec -d "$PRIMARY_MASTER" sh -c \
                "salt --async '*' cp.cache_file '$large_file_salt' >/dev/null 2>&1" \
                >/dev/null 2>&1 || true
            sleep 3
            # Delete, then recreate, mid-fetch.  Whichever minion was mid-
            # transfer should either retry or report a predictable error --
            # neither should crash the minion or corrupt its fileclient.
            docker exec "$PRIMARY_MASTER" sh -c \
                "rm -f '$large_file_path'" >/dev/null 2>&1 || true
            sleep 2
            docker exec "$PRIMARY_MASTER" sh -c \
                "dd if=/dev/zero of='$large_file_path' bs=1M count=${LARGE_FILE_MB} 2>/dev/null" \
                >/dev/null 2>&1 || true
            sleep "$SHORT_FAULT_SEC"
            # Cleanup: remove the probe file so the next run starts clean.
            docker exec "$PRIMARY_MASTER" sh -c \
                "rm -f '$large_file_path'" >/dev/null 2>&1 || true
            fault_end=$(date +%s)
            fault_s=$((fault_end - fault_start))
            assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
                "size_mb=${LARGE_FILE_MB}"  || OVERALL_RC=1
        fi
    fi
    unset label fd_before rss_before large_file_path large_file_salt fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 3: pillar top.sls flip mid-run
# -------------------------------------------------------------------------
{
    label="fs_pillar_flip_mid_run"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: flipping pillar top.sls mid-run"

    pillar_top="$(pick_pillar_top)"
    if [ -z "$pillar_top" ]; then
        log "PHASE ${label}: no pillar top.sls on master, skipping"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "no pillar top.sls on master (TOPOLOGY=$TOPOLOGY has no pillar_roots)"
    elif ! master_srv_salt_writable; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "pillar tree parent is read-only on master"
    else
        PILLAR_TOP_BACKUP="${pillar_top}.bak"
        docker exec "$PRIMARY_MASTER" sh -c \
            "cp -f '$pillar_top' '$PILLAR_TOP_BACKUP'" >/dev/null 2>&1 || true
        fault_start=$(date +%s)
        # Kick a pillar-refreshing operation async.
        docker exec -d "$PRIMARY_MASTER" sh -c \
            "salt --async '*' saltutil.refresh_pillar >/dev/null 2>&1" \
            >/dev/null 2>&1 || true
        sleep 2
        # Mutate: append a harmless comment line.  If we can, also swap
        # an "old" literal for "new" so the user-prompt sed pattern is
        # exercised; absence of "old" just means the sed is a no-op and
        # the append does the work.
        docker exec "$PRIMARY_MASTER" sh -c \
            "sed -i 's/old/new/g' '$pillar_top' 2>/dev/null; \
             printf '\n# resiliency-flip %s\n' \"\$(date -u +%s)\" >> '$pillar_top'" \
            >/dev/null 2>&1 || true
        sleep "$SHORT_FAULT_SEC"
        # Restore from backup.
        restore_pillar_top
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "pillar_top=$pillar_top"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before pillar_top fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 4: /srv/salt remount read-only on master
# -------------------------------------------------------------------------
{
    label="fs_master_srv_remount"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: mount -o remount,ro /srv/salt on ${PRIMARY_MASTER}"

    if ! master_srv_salt_writable; then
        log "PHASE ${label}: /srv/salt is already read-only, no fault to inject"
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "/srv/salt already read-only on $TOPOLOGY topology"
    else
        applied=0
        if docker exec --privileged "$PRIMARY_MASTER" sh -c \
            "mount -o remount,ro /srv/salt 2>/dev/null" >/dev/null 2>&1; then
            applied=1
        else
            # Self-bind + remount ro fallback (needs CAP_SYS_ADMIN too).
            if docker exec --privileged "$PRIMARY_MASTER" sh -c \
                "mount --bind /srv/salt /srv/salt 2>/dev/null \
                    && mount -o remount,ro,bind /srv/salt 2>/dev/null" \
                >/dev/null 2>&1; then
                applied=1
            fi
        fi

        if [ "$applied" = "0" ]; then
            record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
                "mount remount,ro /srv/salt failed (missing CAP_SYS_ADMIN?)"
        else
            SRV_SALT_RO_ACTIVE=1
            fault_start=$(date +%s)
            sleep "$SHORT_FAULT_SEC"
            restore_srv_salt_rw
            fault_end=$(date +%s)
            fault_s=$((fault_end - fault_start))
            assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
                "duration=${SHORT_FAULT_SEC}s"  || OVERALL_RC=1
        fi
    fi
    unset label fd_before rss_before applied fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 5: docker network disconnect on master
# -------------------------------------------------------------------------
{
    label="orch_docker_network_disconnect"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: docker network disconnect $SALT_NET $PRIMARY_MASTER"

    if ! docker network inspect "$SALT_NET" >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "network '$SALT_NET' not found; could not resolve project network"
    elif ! docker network disconnect "$SALT_NET" "$PRIMARY_MASTER" >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "docker network disconnect failed"
    else
        MASTER_NET_DETACHED=1
        fault_start=$(date +%s)
        sleep "$PHASE_DURATION_SEC"
        reconnect_to_net "$PRIMARY_MASTER"
        MASTER_NET_DETACHED=0
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "net=$SALT_NET container=$PRIMARY_MASTER"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 6: docker network disconnect on first minion
# -------------------------------------------------------------------------
{
    label="orch_docker_network_disconnect_minion"
    read -r fd_before rss_before < <(sample_all_minions)
    # First token of MINION_CONTAINERS.
    first_minion=""
    for c in $MINION_CONTAINERS; do first_minion="$c"; break; done
    log "PHASE ${label}: docker network disconnect $SALT_NET $first_minion"

    if [ -z "$first_minion" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "no minion containers in topology"
    elif ! docker network inspect "$SALT_NET" >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "network '$SALT_NET' not found; could not resolve project network"
    elif ! docker network disconnect "$SALT_NET" "$first_minion" >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "docker network disconnect on $first_minion failed"
    else
        MINION_NET_DETACHED=1
        MINION_NET_CONTAINER="$first_minion"
        fault_start=$(date +%s)
        sleep "$PHASE_DURATION_SEC"
        reconnect_to_net "$first_minion"
        MINION_NET_DETACHED=0
        MINION_NET_CONTAINER=""
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "net=$SALT_NET container=$first_minion"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before first_minion fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 7: wipe + recreate /var/cache/salt/master/minions on master
# -------------------------------------------------------------------------
{
    label="orch_volume_remount_simulate"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: rm -rf + recreate /var/cache/salt/master/minions on $PRIMARY_MASTER"

    if ! docker exec "$PRIMARY_MASTER" sh -c \
        '[ -d /var/cache/salt/master ]' >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "/var/cache/salt/master missing on $PRIMARY_MASTER"
    elif ! docker exec "$PRIMARY_MASTER" sh -c \
            'rm -rf /var/cache/salt/master/minions && mkdir -p /var/cache/salt/master/minions' \
            >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "failed to wipe and recreate /var/cache/salt/master/minions"
    else
        MINION_RECORDS_WIPED=1
        fault_start=$(date +%s)
        # Don't hold -- the fault is instantaneous; what we're measuring
        # is how long the master takes to repopulate minion records once
        # pings start arriving again.  Short hold to give ongoing jobs a
        # chance to notice the missing dir.
        sleep "$SHORT_FAULT_SEC"
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        # Dir is already recreated empty; assert_reconnect will drive the
        # repopulation via test.ping.
        MINION_RECORDS_WIPED=0
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "wiped=/var/cache/salt/master/minions"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 8: ip link set $CHOKE_IFACE down (needs CAP_NET_ADMIN)
# -------------------------------------------------------------------------
{
    label="orch_restart_docker_bridge_iface_down"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: ip link set $CHOKE_IFACE down on $CHOKE_CONTAINER"

    applied=0
    if ! docker exec "$CHOKE_CONTAINER" sh -c 'command -v ip >/dev/null 2>&1' \
        >/dev/null 2>&1; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "ip tool missing in $CHOKE_CONTAINER (install iproute2 or run with iproute2 image)"
    elif docker exec --privileged "$CHOKE_CONTAINER" sh -c \
            "ip link set $CHOKE_IFACE down 2>/dev/null" >/dev/null 2>&1; then
        applied=1
        BRIDGE_IFACE_DOWN_ACTIVE=1
        BRIDGE_IFACE_DOWN_CONTAINER="$CHOKE_CONTAINER"
        BRIDGE_IFACE_DOWN_IFACE="$CHOKE_IFACE"
    else
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "ip link set $CHOKE_IFACE down failed (missing CAP_NET_ADMIN?)"
    fi

    if [ "$applied" = "1" ]; then
        fault_start=$(date +%s)
        sleep "$SHORT_FAULT_SEC"
        restore_bridge_iface
        BRIDGE_IFACE_DOWN_CONTAINER=""
        BRIDGE_IFACE_DOWN_IFACE=""
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "choke=$CHOKE_CONTAINER iface=$CHOKE_IFACE"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before applied fault_start fault_end fault_s
}

# -------------------------------------------------------------------------
# Phase 9: random SIGKILL of a non-MainProcess master subprocess
# -------------------------------------------------------------------------
{
    label="orch_random_kill_one_process_tree"
    read -r fd_before rss_before < <(sample_all_minions)
    log "PHASE ${label}: picking a random non-MainProcess master subprocess to SIGKILL"

    # Grab pid + cmdline for every salt-master process that is NOT the
    # MainProcess.  ps output "pid cmd" via docker exec; we filter for
    # 'salt-master' marker, drop lines containing 'MainProcess' or our
    # ps itself, pick a random survivor.
    victim_pid=""
    victim_cmd=""
    ps_out="$(docker exec "$PRIMARY_MASTER" sh -c \
        "ps -eo pid,cmd 2>/dev/null | grep -E 'salt-master' | grep -v 'MainProcess' | grep -v grep || true" \
        2>/dev/null || true)"
    if [ -n "$ps_out" ]; then
        # Shuffle lines; take one.  awk-based because sort -R isn't
        # portable to busybox and shuf may not exist in the image.
        picked="$(printf '%s\n' "$ps_out" | awk '
            BEGIN { srand() }
            { lines[NR] = $0 }
            END { if (NR > 0) print lines[int(rand()*NR)+1] }
        ')"
        victim_pid="$(printf '%s' "$picked" | awk '{print $1}')"
        victim_cmd="$(printf '%s' "$picked" | cut -d' ' -f2-)"
    fi

    if [ -z "$victim_pid" ]; then
        record_result "$label" "setup_error" "-1" "0" "" "0" "0" "0" \
            "no non-MainProcess salt-master subprocess found on $PRIMARY_MASTER"
    else
        log "PHASE ${label}: SIGKILL pid=$victim_pid cmd=$victim_cmd"
        fault_start=$(date +%s)
        docker exec "$PRIMARY_MASTER" sh -c "kill -9 $victim_pid 2>/dev/null" \
            >/dev/null 2>&1 || true
        # Give the ProcessManager a short window to respawn before we start
        # banging on test.ping.
        sleep "$SHORT_FAULT_SEC"
        fault_end=$(date +%s)
        fault_s=$((fault_end - fault_start))
        # Trimmed cmd for notes (avoid dumping full cmdline into results).
        short_cmd="$(printf '%s' "$victim_cmd" | cut -c1-80)"
        assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
            "killed_pid=$victim_pid cmd=$short_cmd"  || OVERALL_RC=1
    fi
    unset label fd_before rss_before victim_pid victim_cmd picked ps_out short_cmd fault_start fault_end fault_s
}

log "fileserver_orch scenario complete; results in ${RESULTS_FILE}"

exit "$OVERALL_RC"
