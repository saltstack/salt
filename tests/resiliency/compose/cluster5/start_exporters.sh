#!/usr/bin/env bash
# Launch fd_exporter.py inside each salt-master container of the
# cluster-5node topology.
#
# Compose can't cleanly override the command/entrypoint of a service
# defined in the base compose from an overlay (overlay ``command:``
# replaces the base one wholesale), so the resiliency orchestrator
# invokes this script after ``docker compose up -d`` returns.
#
# The base cluster-5node compose mounts ``./srv/salt:/srv/salt`` (pillar
# + states only) -- it does NOT ship the exporter.  The resiliency
# ``monitoring-overlay.yml`` adds a second volume per master that binds
# ``tests/monitoring/srv/salt/fd_exporter.py:/usr/local/bin/fd_exporter.py``
# so this script can exec a stable path regardless of what the base
# mount contains.  It listens on 0.0.0.0:8002 inside the master
# container; prometheus.yml in this dir scrapes it by the service
# hostname (salt-master-N:8002) over salt-net.
#
# Re-running this script is safe -- fd_exporter.py binds a fixed port,
# so a second instance will fail fast and the first keeps serving.

set -euo pipefail

MASTERS=(c5-salt-master-1 c5-salt-master-2 c5-salt-master-3 c5-salt-master-4 c5-salt-master-5)

for m in "${MASTERS[@]}"; do
    if ! docker inspect -f '{{.State.Running}}' "$m" 2>/dev/null | grep -q true; then
        printf 'start_exporters: container %s is not running, skipping\n' "$m" >&2
        continue
    fi
    # -d = detached; stdout/stderr land in docker logs of the master itself,
    # which is fine for a diagnostic process.
    docker exec -d "$m" python3 /usr/local/bin/fd_exporter.py
    printf 'start_exporters: launched fd_exporter in %s\n' "$m"
done
