#!/usr/bin/env bash
# Launch fd_exporter.py inside the single-topology master.
# Mirrors cluster3's start_exporters.sh for symmetry.  The exporter is
# bind-mounted at /usr/local/bin/fd_exporter.py by the single compose
# file, so this script is topology-agnostic except for the container
# name list.

set -euo pipefail

MASTERS=(rs-single-salt-master)

for m in "${MASTERS[@]}"; do
    if ! docker inspect -f '{{.State.Running}}' "$m" 2>/dev/null | grep -q true; then
        printf 'start_exporters: container %s is not running, skipping\n' "$m" >&2
        continue
    fi
    docker exec -d "$m" python3 /usr/local/bin/fd_exporter.py
    printf 'start_exporters: launched fd_exporter in %s\n' "$m"
done
