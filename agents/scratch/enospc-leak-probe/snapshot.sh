#!/bin/bash
# Snapshot per-process fd/rss on cluster3 masters + minions.
# Output TSV appended to $2: tag\tcontainer\tpid\tfds\trss_kb\tcmd
set -u
tag="${1:-unset}"
out="${2:-/dev/stdout}"
probe=/tmp/probe.sh.$$

cat > "$probe" <<'SH'
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
SH

for ctr in c3-salt-master-1 c3-salt-master-2 c3-salt-master-3 \
           c3-salt-minion-1 c3-salt-minion-2 c3-salt-minion-3 \
           c3-salt-minion-4 c3-salt-minion-5; do
  docker cp "$probe" "$ctr":/tmp/probe.sh 2>/dev/null
  docker exec "$ctr" sh /tmp/probe.sh 2>/dev/null \
    | awk -F'\t' -v tag="$tag" -v ctr="$ctr" '{printf "%s\t%s\t%s\t%s\t%s\t%s\n", tag, ctr, $1, $2, $3, $4}' \
    >> "$out"
done

rm -f "$probe"
