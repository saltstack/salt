#!/bin/bash
# RSS stability probe for saltop_* bulk_rss tests on single topology.
#
# For each test, we:
#   1. Sample minion fleet RSS baseline
#   2. Trigger the fault
#   3. Immediately resample ("during")
#   4. Wait 60s, resample ("+60s")
#   5. Wait another 60s, resample ("+120s")
#   6. Wait another 60s, resample ("+180s")
#
# If +60s / +120s / +180s samples plateau within noise (< 500 KB
# spread), the growth is bulk-cache population, not a leak.
# If they keep climbing, it's a real leak.
set -eu

MASTER=rs-single-salt-master
MINIONS=(rs-single-salt-minion-1 rs-single-salt-minion-2 rs-single-salt-minion-3)
FIRST_MINION_ID="salt-minion-1"
FIRST_MINION_CTR="rs-single-salt-minion-1"

sample_fleet_fd() {
    local total=0
    for c in "${MINIONS[@]}"; do
        local pid
        pid=$(docker exec "$c" sh -c "pgrep -f 'salt-minion.*MinionProcessManager\$' | head -1" 2>/dev/null)
        [ -z "$pid" ] && pid=$(docker exec "$c" sh -c "pgrep -f 'salt-minion.*MainProcess\$' | head -1" 2>/dev/null)
        [ -z "$pid" ] && continue
        local fd
        fd=$(docker exec "$c" sh -c "ls /proc/$pid/fd 2>/dev/null | wc -l" 2>/dev/null)
        [ -z "$fd" ] && fd=0
        total=$((total + fd))
    done
    echo "$total"
}

sample_fleet_rss() {
    # Match the resiliency suite's sampling (tests/resiliency/lib/topology.py:_PID_SH):
    # MinionProcessManager child is where the real minion work happens.
    local total=0
    for c in "${MINIONS[@]}"; do
        local pid
        pid=$(docker exec "$c" sh -c "pgrep -f 'salt-minion.*MinionProcessManager\$' | head -1" 2>/dev/null)
        [ -z "$pid" ] && pid=$(docker exec "$c" sh -c "pgrep -f 'salt-minion.*MainProcess\$' | head -1" 2>/dev/null)
        [ -z "$pid" ] && continue
        local rss
        rss=$(docker exec "$c" sh -c "awk '/VmRSS/ {print \$2}' /proc/$pid/status 2>/dev/null" 2>/dev/null)
        [ -z "$rss" ] && rss=0
        total=$((total + rss))
    done
    echo "$total"
}

label_sample() {
    local label=$1
    local rss fd
    rss=$(sample_fleet_rss)
    fd=$(sample_fleet_fd)
    printf '%-14s  rss_kb=%d  fd=%d\n' "$label" "$rss" "$fd"
}

run_test() {
    local test_name=$1
    local fault_fn=$2
    echo "=== $test_name ==="
    label_sample "baseline"
    "$fault_fn"
    label_sample "during"
    sleep 60
    label_sample "+60s"
    sleep 60
    label_sample "+120s"
    sleep 60
    label_sample "+180s"
    echo
}

fault_pillar_refresh() {
    docker exec "$MASTER" salt --async '*' state.apply >/dev/null 2>&1 || true
    docker exec "$MASTER" salt --async '*' saltutil.refresh_pillar >/dev/null 2>&1 || true
    sleep 15  # let both jobs propagate
}

fault_beacon_flood() {
    docker exec "$FIRST_MINION_CTR" sh -c "mkdir -p /etc/salt/minion.d && cat > /etc/salt/minion.d/beacon-flood.conf <<EOF
beacons:
  status:
    - interval: 1
EOF" || true
    docker exec "$MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_beacons >/dev/null 2>&1 || true
    sleep 30  # hold the flood briefly
    docker exec "$FIRST_MINION_CTR" rm -f /etc/salt/minion.d/beacon-flood.conf || true
    docker exec "$MASTER" salt "$FIRST_MINION_ID" saltutil.refresh_beacons >/dev/null 2>&1 || true
}

fault_cache_corruption() {
    local cache_dir="/var/cache/salt/master/minions/$FIRST_MINION_ID"
    docker exec "$MASTER" sh -c "test -d '$cache_dir' || mkdir -p '$cache_dir'; : > '$cache_dir/data.p'" || true
    docker exec "$MASTER" salt --timeout=15 "$FIRST_MINION_ID" grains.items >/dev/null 2>&1 || true
    sleep 5
}

fault_sls_swap() {
    # Mirror test_fs_sls_swap_mid_state: fire state.apply async then
    # swap top.sls content mid-flight.  Minions download the SLS and
    # file artifacts during the state run.
    docker exec -d "$MASTER" sh -c \
        "salt --async '*' state.apply heavy >/dev/null 2>&1 || salt --async '*' state.apply >/dev/null 2>&1" || true
    sleep 3
    docker exec "$MASTER" sh -c "echo '# swapped' > /srv/salt/top.sls.bak && cp /srv/salt/top.sls /srv/salt/top.sls.bak" || true
    sleep 20
}

run_test "pillar_refresh" fault_pillar_refresh
run_test "beacon_flood" fault_beacon_flood
run_test "cache_corruption" fault_cache_corruption
run_test "sls_swap" fault_sls_swap
