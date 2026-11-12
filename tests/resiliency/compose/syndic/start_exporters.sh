#!/usr/bin/env bash
# Launch fd_exporter.py inside each salt-master container of the syndic
# resiliency topology (MoM + sub-master).
#
# The fd_exporter has to run *inside* each master container so it can
# read /proc of the master processes directly; compose can't model that
# as a service.  The orchestrator calls this script after
# ``docker compose up -d`` returns.
#
# The compose file binds
# ``tests/monitoring/srv/salt/fd_exporter.py:/usr/local/bin/fd_exporter.py``
# in both masters, so this script just exec's the stable path.  The
# exporter listens on 0.0.0.0:8002; prometheus.yml in this dir scrapes
# the service hostnames rs-syndic-mom:8002 and rs-syndic-sub:8002 over
# salt-net.
#
# Re-running this script is safe -- fd_exporter.py binds a fixed port,
# so a second instance will fail fast and the first keeps serving.

set -euo pipefail

MASTERS=(rs-syndic-mom rs-syndic-sub)

for m in "${MASTERS[@]}"; do
    if ! docker inspect -f '{{.State.Running}}' "$m" 2>/dev/null | grep -q true; then
        printf 'start_exporters: container %s is not running, skipping\n' "$m" >&2
        continue
    fi
    docker exec -d "$m" python3 /usr/local/bin/fd_exporter.py
    printf 'start_exporters: launched fd_exporter in %s\n' "$m"
done
