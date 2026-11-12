#!/usr/bin/env bash
#
# Resiliency scenario: Salt operator / control-plane fault battery.
#
# Each phase exercises a different "normal thing an operator (or a buggy
# downstream caller) does to a running cluster" and asserts that the
# cluster still passes assert_reconnect afterwards.
#
# Phases:
#   1.  saltop_key_reject                     -- salt-key -d a minion; auto_accept re-auths it
#   2.  saltop_master_pem_truncate_recover    -- truncate master.pem then restore + SIGHUP;
#                                                proves in-memory key state is authoritative
#   3.  saltop_grain_mutation                 -- append custom grain mid-flight + refresh_grains
#   4.  saltop_pillar_refresh_during_state    -- state.apply --async racing refresh_pillar
#   5.  saltop_kill_job_mid_flight            -- state.sleep 60 then saltutil.kill_job <jid>
#   6.  saltop_event_storm                    -- fire 10k events at the master bus
#   7.  saltop_beacon_flood                   -- status beacon on first minion for 60s
#   8.  saltop_mine_burst                     -- mine.update --async in a tight loop for 60s
#   9.  saltop_cache_corruption               -- truncate master-side cache/data.p for a minion
#
# Every phase ends with an assert_reconnect call that records one
# results.jsonl row.  A failure in one phase does NOT short-circuit the
# rest; the overall exit code is 1 if any phase failed.
#
# Destructive-adjacent phase (saltop_master_pem_truncate_recover):
#   - A backup of /etc/salt/pki/master/master.pem is taken to
#     /tmp/.bk INSIDE the master container BEFORE truncation.  If a
#     backup from a previous aborted run is already present, it is
#     reused rather than overwritten (the first failed run captured the
#     known-good copy; a second attempt after corruption would overwrite
#     the good backup with the broken file).
#   - A script-wide EXIT trap restores the backup + SIGHUPs the master
#     unconditionally, so an abort between truncate and restore still
#     leaves the master usable.
#   - If backup creation fails OR restore fails, the phase records
#     setup_error and skips assert_reconnect -- running a ping battery
#     against a master with no private key would just time out with
#     misleading data.
#
# Env tunables (all have defaults):
#   INTER_PHASE_WAIT_SEC   15   seconds between phases
#   KEY_REJECT_HOLD_SEC    30   how long to leave the key rejected
#   PEM_TRUNCATE_HOLD_SEC  10   how long to hold the truncated master.pem
#   BEACON_HOLD_SEC        60   how long to leave the beacon flood on
#   MINE_BURST_SEC         60   duration of the mine.update loop
#   KILL_JOB_WAIT_SEC      15   seconds after state.sleep before kill_job

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/common.sh
. "${SCRIPT_DIR}/../lib/common.sh"

load_topology

: "${INTER_PHASE_WAIT_SEC:=15}"
: "${KEY_REJECT_HOLD_SEC:=30}"
: "${PEM_TRUNCATE_HOLD_SEC:=10}"
: "${BEACON_HOLD_SEC:=60}"
: "${MINE_BURST_SEC:=60}"
: "${KILL_JOB_WAIT_SEC:=15}"

OVERALL_RC=0

# First minion id + container (phases that target "a single minion" pick
# element 0 of the respective list; keeping both in lockstep because
# load_topology emits them in matching order).
FIRST_MINION_ID="$(printf '%s\n' $MINION_IDS | head -1)"
FIRST_MINION_CTR="$(printf '%s\n' $MINION_CONTAINERS | head -1)"

# ---------------------------------------------------------------------------
# Trap: master.pem restore + grains restore on any exit path.
# ---------------------------------------------------------------------------
PEM_BACKUP_INSIDE="/tmp/.master.pem.resiliency.bk"
GRAINS_BACKUP_INSIDE="/tmp/.grains.resiliency.bk"
PEM_TRAP_ARMED=0
GRAINS_TRAP_ARMED=0

cleanup_on_exit() {
    local rc=$?
    if [ "$PEM_TRAP_ARMED" = "1" ]; then
        log "trap: restoring master.pem from ${PEM_BACKUP_INSIDE} on ${PRIMARY_MASTER}"
        docker exec "$PRIMARY_MASTER" sh -c "
            if [ -s '${PEM_BACKUP_INSIDE}' ]; then
                cp '${PEM_BACKUP_INSIDE}' /etc/salt/pki/master/master.pem
                chmod 400 /etc/salt/pki/master/master.pem
                pkill -HUP -f salt-master || true
            fi
        " >/dev/null 2>&1 || log "trap: master.pem restore returned non-zero"
    fi
    if [ "$GRAINS_TRAP_ARMED" = "1" ]; then
        log "trap: restoring /etc/salt/grains on ${FIRST_MINION_CTR}"
        docker exec "$FIRST_MINION_CTR" sh -c "
            if [ -f '${GRAINS_BACKUP_INSIDE}' ]; then
                cp '${GRAINS_BACKUP_INSIDE}' /etc/salt/grains
            else
                : > /etc/salt/grains
            fi
        " >/dev/null 2>&1 || log "trap: grains restore returned non-zero"
    fi
    # Best-effort beacon config cleanup; harmless if the file isn't there.
    docker exec "$FIRST_MINION_CTR" sh -c "
        rm -f /etc/salt/minion.d/beacon-flood.conf
    " >/dev/null 2>&1 || true
    exit "$rc"
}
trap cleanup_on_exit EXIT INT TERM

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
# Phase 1: salt-key -d <first-minion-id>
# ---------------------------------------------------------------------------
# With auto_accept on (resiliency compose default), the minion detects
# rejection at the next auth cycle and re-auths; the re-accept below is
# a belt-and-suspenders no-op for auto_accept and the actual recovery
# path for topologies that disable auto_accept.
phase_key_reject() {
    local label="saltop_key_reject"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    log "phase '$label': rejecting key for ${FIRST_MINION_ID}"
    fault_start=$(date +%s)
    if ! docker exec "$PRIMARY_MASTER" salt-key -d "$FIRST_MINION_ID" -y >/dev/null 2>&1; then
        record_setup_error "$label" "salt-key -d ${FIRST_MINION_ID} failed"
        return 1
    fi
    sleep "$KEY_REJECT_HOLD_SEC"
    log "phase '$label': re-accepting ${FIRST_MINION_ID}"
    docker exec "$PRIMARY_MASTER" salt-key -y -a "$FIRST_MINION_ID" >/dev/null 2>&1 || true
    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 2: master.pem truncate + recover
# ---------------------------------------------------------------------------
phase_master_pem_truncate_recover() {
    local label="saltop_master_pem_truncate_recover"
    local fd_before rss_before fault_start fault_end

    # Reuse an existing backup if a prior run aborted after truncation;
    # otherwise capture a fresh copy of the current (known-good) pem.
    log "phase '$label': ensuring backup at ${PEM_BACKUP_INSIDE}"
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        if [ ! -s '${PEM_BACKUP_INSIDE}' ]; then
            cp /etc/salt/pki/master/master.pem '${PEM_BACKUP_INSIDE}' || exit 1
        fi
        test -s '${PEM_BACKUP_INSIDE}'
    "; then
        record_setup_error "$label" "could not create or verify master.pem backup"
        return 1
    fi
    PEM_TRAP_ARMED=1

    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)
    log "phase '$label': truncating /etc/salt/pki/master/master.pem"
    if ! docker exec "$PRIMARY_MASTER" sh -c ": > /etc/salt/pki/master/master.pem"; then
        record_setup_error "$label" "truncation command failed"
        return 1
    fi

    sleep "$PEM_TRUNCATE_HOLD_SEC"

    log "phase '$label': restoring master.pem from ${PEM_BACKUP_INSIDE}"
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        cp '${PEM_BACKUP_INSIDE}' /etc/salt/pki/master/master.pem \
        && chmod 400 /etc/salt/pki/master/master.pem \
        && test -s /etc/salt/pki/master/master.pem
    "; then
        record_setup_error "$label" "restore from backup failed"
        # Leave PEM_TRAP_ARMED=1 so the exit trap retries the restore.
        return 1
    fi

    log "phase '$label': SIGHUP salt-master"
    docker exec "$PRIMARY_MASTER" sh -c "pkill -HUP -f salt-master || true" >/dev/null 2>&1 || true

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))

    # Restore succeeded; we can disarm the trap for this file.  Keep the
    # backup file in place (harmless; cleaned up when the container is
    # torn down) so a re-run inside the same container still finds it.
    PEM_TRAP_ARMED=0

    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" \
        "master.pem truncated for ${PEM_TRUNCATE_HOLD_SEC}s"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 3: grain mutation mid-flight
# ---------------------------------------------------------------------------
phase_grain_mutation() {
    local label="saltop_grain_mutation"
    local fd_before rss_before fault_start fault_end

    log "phase '$label': backing up /etc/salt/grains on ${FIRST_MINION_CTR}"
    if ! docker exec "$FIRST_MINION_CTR" sh -c "
        if [ -f /etc/salt/grains ]; then
            cp /etc/salt/grains '${GRAINS_BACKUP_INSIDE}'
        else
            : > '${GRAINS_BACKUP_INSIDE}'
        fi
    "; then
        record_setup_error "$label" "grains backup failed"
        return 1
    fi
    GRAINS_TRAP_ARMED=1

    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': appending custom_grain to /etc/salt/grains"
    if ! docker exec "$FIRST_MINION_CTR" sh -c "echo 'custom_grain: changed' >> /etc/salt/grains"; then
        record_setup_error "$label" "grain append failed"
        return 1
    fi

    log "phase '$label': saltutil.refresh_grains"
    docker exec "$PRIMARY_MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_grains >/dev/null 2>&1 || true

    # Poll up to RECONNECT_WINDOW_SEC for grains.item to reflect the new value.
    local deadline=$(( $(date +%s) + RECONNECT_WINDOW_SEC ))
    local saw_grain=0
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if docker exec "$PRIMARY_MASTER" salt --timeout=10 --out=json "$FIRST_MINION_ID" \
            grains.item custom_grain 2>/dev/null | grep -q '"changed"'; then
            saw_grain=1
            break
        fi
        sleep 2
    done

    log "phase '$label': restoring grains from backup"
    docker exec "$FIRST_MINION_CTR" sh -c "cp '${GRAINS_BACKUP_INSIDE}' /etc/salt/grains" >/dev/null 2>&1 || true
    docker exec "$PRIMARY_MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_grains >/dev/null 2>&1 || true
    GRAINS_TRAP_ARMED=0

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    local notes=""
    if [ "$saw_grain" -ne 1 ]; then
        notes="custom_grain did not appear within ${RECONNECT_WINDOW_SEC}s"
        log "phase '$label': WARNING - $notes"
        OVERALL_RC=1
    fi

    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 4: pillar refresh racing a state.apply
# ---------------------------------------------------------------------------
phase_pillar_refresh_during_state() {
    local label="saltop_pillar_refresh_during_state"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': kicking state.apply --async + racing refresh_pillar"
    local state_jid
    state_jid="$(docker exec "$PRIMARY_MASTER" salt --out=json --async '*' state.apply 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('jid','') if isinstance(d,dict) else '')" 2>/dev/null || true)"
    docker exec "$PRIMARY_MASTER" salt --async '*' saltutil.refresh_pillar >/dev/null 2>&1 || true

    # Wait for the state JID to drain from the running-jobs list, but
    # cap at RECONNECT_WINDOW_SEC so a hang here does not consume the
    # whole battery budget.
    local deadline=$(( $(date +%s) + RECONNECT_WINDOW_SEC ))
    local drained=1
    if [ -n "$state_jid" ]; then
        drained=0
        while [ "$(date +%s)" -lt "$deadline" ]; do
            if ! docker exec "$PRIMARY_MASTER" salt-run --out=json jobs.active 2>/dev/null \
                | grep -q "\"${state_jid}\""; then
                drained=1
                break
            fi
            sleep 3
        done
    fi
    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    local notes=""
    if [ "$drained" -ne 1 ]; then
        notes="state jid ${state_jid} still active after ${RECONNECT_WINDOW_SEC}s"
        OVERALL_RC=1
    fi

    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "$notes"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 5: kill a long-running job mid-flight
# ---------------------------------------------------------------------------
phase_kill_job_mid_flight() {
    local label="saltop_kill_job_mid_flight"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': dispatching state.sleep 60 --async"
    local jid
    jid="$(docker exec "$PRIMARY_MASTER" salt --out=json --async '*' state.sleep 60 2>/dev/null \
        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('jid','') if isinstance(d,dict) else '')" 2>/dev/null || true)"
    if [ -z "$jid" ]; then
        # Fall back to scraping salt-run jobs.list_jobs for the most
        # recent state.sleep jid; keeps the phase meaningful even when
        # --out=json emits a non-dict on some topologies.
        jid="$(docker exec "$PRIMARY_MASTER" salt-run --out=json jobs.list_jobs 2>/dev/null \
            | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)
cands = [(k,v) for k,v in data.items() if isinstance(v,dict) and v.get('Function')=='state.sleep']
if cands:
    cands.sort(key=lambda kv: kv[0], reverse=True)
    print(cands[0][0])
" 2>/dev/null || true)"
    fi

    if [ -z "$jid" ]; then
        record_setup_error "$label" "could not determine state.sleep JID"
        return 1
    fi
    log "phase '$label': state.sleep JID=${jid}; waiting ${KILL_JOB_WAIT_SEC}s before kill"
    sleep "$KILL_JOB_WAIT_SEC"

    log "phase '$label': saltutil.kill_job ${jid}"
    docker exec "$PRIMARY_MASTER" salt '*' saltutil.kill_job "$jid" >/dev/null 2>&1 || true

    # Confirm next test.ping still goes through (quick spot-check; the
    # real criterion is assert_reconnect below).
    docker exec "$PRIMARY_MASTER" salt --timeout=10 '*' test.ping >/dev/null 2>&1 || true

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" "killed_jid=${jid}"; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 6: event-bus storm
# ---------------------------------------------------------------------------
phase_event_storm() {
    local label="saltop_event_storm"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': firing 10000 events at master bus"
    docker exec "$PRIMARY_MASTER" python3 -c "
import salt.utils.event, salt.config
opts = salt.config.master_config('/etc/salt/master')
e = salt.utils.event.get_event('master', opts=opts)
for i in range(10000):
    e.fire_event({'n': i}, 'stress/test')
" >/dev/null 2>&1 || log "phase '$label': event storm script returned non-zero (continuing)"

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 7: beacon flood
# ---------------------------------------------------------------------------
phase_beacon_flood() {
    local label="saltop_beacon_flood"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': installing status beacon on ${FIRST_MINION_CTR}"
    if ! docker exec "$FIRST_MINION_CTR" sh -c "mkdir -p /etc/salt/minion.d && cat > /etc/salt/minion.d/beacon-flood.conf <<'EOF'
beacons:
  status:
    - interval: 1
EOF"; then
        record_setup_error "$label" "writing beacon-flood.conf failed"
        return 1
    fi
    docker exec "$PRIMARY_MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_beacons >/dev/null 2>&1 || true

    log "phase '$label': holding beacon flood for ${BEACON_HOLD_SEC}s"
    sleep "$BEACON_HOLD_SEC"

    log "phase '$label': removing beacon-flood.conf"
    docker exec "$FIRST_MINION_CTR" sh -c "rm -f /etc/salt/minion.d/beacon-flood.conf" >/dev/null 2>&1 || true
    docker exec "$PRIMARY_MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_beacons >/dev/null 2>&1 || true

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 8: mine burst
# ---------------------------------------------------------------------------
phase_mine_burst() {
    local label="saltop_mine_burst"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': mine.update --async loop for ${MINE_BURST_SEC}s"
    local end=$(( $(date +%s) + MINE_BURST_SEC ))
    while [ "$(date +%s)" -lt "$end" ]; do
        docker exec "$PRIMARY_MASTER" salt --async '*' mine.update >/dev/null 2>&1 || true
    done

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Phase 9: cache corruption (truncate minion's cached grains)
# ---------------------------------------------------------------------------
phase_cache_corruption() {
    local label="saltop_cache_corruption"
    local fd_before rss_before fault_start fault_end
    read -r fd_before rss_before < <(sample_all_minions)
    fault_start=$(date +%s)

    log "phase '$label': truncating master cache data.p for ${FIRST_MINION_ID}"
    if ! docker exec "$PRIMARY_MASTER" sh -c "
        test -d /var/cache/salt/master/minions/${FIRST_MINION_ID} \
            || mkdir -p /var/cache/salt/master/minions/${FIRST_MINION_ID}
        : > /var/cache/salt/master/minions/${FIRST_MINION_ID}/data.p
    "; then
        record_setup_error "$label" "cache truncation failed"
        return 1
    fi

    # Force regeneration via a grains fetch.  The master should repopulate
    # data.p from the live minion response.
    docker exec "$PRIMARY_MASTER" salt --timeout=15 "$FIRST_MINION_ID" grains.items >/dev/null 2>&1 || true

    fault_end=$(date +%s)
    local fault_s=$((fault_end - fault_start))
    if ! assert_reconnect "$label" "$fault_s" "$fd_before" "$rss_before" ""; then
        OVERALL_RC=1
    fi
}

# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------
phase_key_reject;                       between_phases
phase_master_pem_truncate_recover;      between_phases
phase_grain_mutation;                   between_phases
phase_pillar_refresh_during_state;      between_phases
phase_kill_job_mid_flight;              between_phases
phase_event_storm;                      between_phases
phase_beacon_flood;                     between_phases
phase_mine_burst;                       between_phases
phase_cache_corruption

log "salt_ops battery complete; overall_rc=${OVERALL_RC}"
exit "$OVERALL_RC"
