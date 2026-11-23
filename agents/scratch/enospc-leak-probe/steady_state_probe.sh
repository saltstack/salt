#!/bin/bash
# 30-minute steady-state workload probe for cluster3.
# Fires continuous wildcard workload from c3-salt-master-1 (same scripts
# the test workload fixture uses), snapshots per-process fd/rss on all
# master + minion containers every 90s.  Output TSV at $OUT.

set -u
OUT="${1:-agents/scratch/enospc-leak-probe/steady.tsv}"
DURATION="${DURATION:-1800}"   # 30 min default
INTERVAL="${INTERVAL:-90}"     # 90s between snapshots

> "$OUT"
PRIMARY=c3-salt-master-1

# -------------------- start workload loops (background) --------------------
# Three loops: test.ping every 5s, async grains.items every 15s, async
# state.apply every 30s.  Match tests/resiliency/workload.sh.
(
  while true; do
    docker exec "$PRIMARY" salt --timeout=10 '*' test.ping >/dev/null 2>&1 || true
    sleep 5
  done
) &
WL_PING_PID=$!

(
  while true; do
    docker exec "$PRIMARY" salt --async '*' grains.items >/dev/null 2>&1 || true
    sleep 15
  done
) &
WL_GRAINS_PID=$!

(
  while true; do
    docker exec "$PRIMARY" salt --async '*' state.apply >/dev/null 2>&1 || true
    sleep 30
  done
) &
WL_STATE_PID=$!

echo "workload loops: ping=$WL_PING_PID grains=$WL_GRAINS_PID state=$WL_STATE_PID"

# -------------------- cleanup trap --------------------
cleanup() {
  kill $WL_PING_PID $WL_GRAINS_PID $WL_STATE_PID 2>/dev/null
  wait 2>/dev/null
  echo "workload stopped at $(date +%T)"
}
trap cleanup EXIT

# -------------------- snapshot loop --------------------
# Copy probe script into containers once (same as snapshot.sh).
cat > /tmp/probe.sh.ss <<'PROBE'
for pid_dir in /proc/[0-9]*; do
  pid="${pid_dir##*/}"
  [ -d "$pid_dir/fd" ] || continue
  fds=$(ls "$pid_dir/fd/" 2>/dev/null | wc -l)
  rss=$(awk '/^VmRSS:/{print $2; exit}' "$pid_dir/status" 2>/dev/null)
  rss=${rss:-0}
  cmd=$(tr '\0' ' ' < "$pid_dir/cmdline" 2>/dev/null | tr -s ' ' | sed 's/ $//' | cut -c1-80)
  [ -z "$cmd" ] && continue
  printf "%s\t%d\t%d\t%s\n" "$pid" "$fds" "$rss" "$cmd"
done
PROBE

for ctr in c3-salt-master-1 c3-salt-master-2 c3-salt-master-3 \
           c3-salt-minion-1 c3-salt-minion-2 c3-salt-minion-3 \
           c3-salt-minion-4 c3-salt-minion-5; do
  docker cp /tmp/probe.sh.ss "$ctr":/tmp/probe.sh.ss 2>/dev/null
done

start_ts=$(date +%s)
iter=0
while true; do
  now=$(date +%s)
  elapsed=$((now - start_ts))
  if [ $elapsed -ge $DURATION ]; then
    echo "probe done after $elapsed seconds"
    break
  fi
  iter=$((iter + 1))
  tag="T+${elapsed}s"
  for ctr in c3-salt-master-1 c3-salt-master-2 c3-salt-master-3 \
             c3-salt-minion-1 c3-salt-minion-2 c3-salt-minion-3 \
             c3-salt-minion-4 c3-salt-minion-5; do
    docker exec "$ctr" sh /tmp/probe.sh.ss 2>/dev/null \
      | awk -F'\t' -v tag="$tag" -v ctr="$ctr" -v ts="$now" \
        '{printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n", tag, ts, ctr, $1, $2, $3, $4}' \
      >> "$OUT"
  done
  echo "iter $iter  $tag  $(wc -l < $OUT) lines"
  sleep $INTERVAL
done
