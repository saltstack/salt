# cluster3 disk-exhaustion diagnostic instrumentation

**Date:** 2026-11-16
**Branch:** `dwoz/resiliency-test-suite`
**Context:** cluster3 resiliency job dies at ~2.5-3h with step `conclusion=null`,
logs blob 404, and no artifact upload. Agent K's prior `Collect Logs on Failure`
+ `Disk preflight` steps produce zero data because the GHA worker process
crashes before any `if: always()` / `if: failure()` hook can fire.

## Artifact audit (run 43824366115)

Downloaded all surviving artifacts from the failed run. cluster3 has no
artifact (never uploaded). Sizes of the two closest topologies:

| Topology | Zip size | Unpacked total | Top 3 files |
|---|---|---|---|
| single | 34 MB | **601 MB** | `rs-single-salt-minion-{1,2,3}.log` = 187/191/190 MB each |
| cluster5 | 34 MB | **998 MB** | `c5-salt-master-{3,4,5}.log` = **325/317/317 MB each** |

The 300+ MB per-master cluster5 logs are dominated by two repeating patterns:

- `[Errno 22] Invalid argument` tracebacks (17,496 reps in the first 20 MB slice
  of `c5-salt-master-3.log`, pointing at `getattr(self.obj, key)(*args, **kwargs)`
  in `tornado.ioloop.run_sync` under the `on read:` path)
- `to forward event to cluster peer salt-master-N; resetting pusher for reconnect`
  (8,828 / 8,871 reps per-peer)

Both are container stdout/stderr, which Docker's json-file driver persists to
`/var/lib/docker/containers/<id>/<id>-json.log` on the runner's root filesystem
until `docker rm`.

## Hypothesis on what fills cluster3 disk

ubuntu-latest ships with ~14 GB free on `/`. A 3-master cluster3 run at
3h is likely producing:

- 3 masters × ~400 MB (scaling from cluster5's ~330 MB per master at ~1h earlier
  crash) × ≥2 (longer runtime before crash) = **~2.4 GB of container json.log**
- 3 minions × ~200 MB (single topology's rate) = **~600 MB**
- docker image layers for `cluster-3node-salt:latest` + prometheus + cadvisor
  base images = ~2 GB
- buildx cache in `/tmp/.buildx-cache` = ~1-2 GB
- `/home/runner/runners/*/_diag/Worker_*.log` growing with every step (the
  precedent failure site for the ENOSPC)
- prometheus TSDB in `tests/resiliency/compose/cluster3/prometheus_data/`
  (~20-25 MB per topology in our audit, bounded)

Peak estimate ~8-10 GB used out of 14 GB free — within one error-storm burst
of hitting ENOSPC. The Errno 22 traceback storm is a strong candidate because
it writes several bytes per line at hundreds of lines/sec sustained.

Running prometheus restart-loops (the 43773954141 prometheus_data chown bug,
fixed by `bf9d8ae4738`) would multiply this. Even with that fix, the
container log pattern alone suffices.

## Instrumentation added

**`.github/workflows/nightly-resiliency-test.yml`:**

### 1. `Start disk trace (background)` step, BEFORE `Start environment`

Two independent 60-second-interval disk-usage loggers:

- **Host-side bash loop** `setsid`'d + `disown`'d so it survives the step's
  process group being killed. Writes to
  `${GITHUB_WORKSPACE}/artifacts/disk-trace/host-trace.log`. Each sample:
  - `df -h / /tmp /var/lib/docker`
  - `du -sh /var/lib/docker` + top-15 `/tmp/*` by size
  - `docker ps --size` (per-container fs usage)
  - top-20 `/var/lib/docker/containers/*/*-json.log` sizes
  - `/home/runner/runners/*/_diag` size + listing (the precedent crash site)

- **Alpine helper container** `c3-disk-logger` with `--pid=host` + RO bind on
  `/var/lib/docker` + writable bind on the artifacts dir. Survives the
  worker's Python process dying as long as `dockerd` is alive — which is
  specifically the current failure mode. Writes to
  `artifacts/disk-trace/container-trace.log`.

Both loggers are robust to the worker dying: the host logger via setsid
detachment, the container logger via Docker-daemon independence.

### 2. `Stop disk trace` step, AFTER `Start environment` with `if: always()`

Best-effort cleanup: kill the host logger pid-group, `docker rm -f
c3-disk-logger`, and write a `FINAL` sample so the trace file has a known
terminal entry.

### 3. `Collect Logs on Failure` hardening

- Cap each `docker logs <c>` dump at the last 200,000 lines or 50 MB (whichever
  is smaller) via `--tail 200000 | tail -c 52428800`. A 3-master cluster3 on
  an already-OOMed worker cannot afford to dump full 300+ MB streams
  uncompressed.
- Add top-20 container `json.log` size dump to `disk-usage.txt`.

## What the trace captures at each crash point

If the worker dies mid-run:

1. The container logger keeps running (writes to the artifacts dir on the
   runner's local disk via the bind mount). Next scheduled run of `df -h` +
   `du -sh /var/lib/docker/containers/*/*-json.log` will show which
   container's log hit the wall and roughly when.
2. The host logger may or may not survive (depends on whether the OOM
   killer walks the setsid process tree). If it does, it also captures
   `_diag/Worker_*.log` growth.
3. If the worker survives enough to run Upload Artifacts, the trace rides
   out in `artifacts/disk-trace/`.
4. If it doesn't, the trace at least lives on the ephemeral runner until
   GHA reaps it — not currently retrievable, but next step would be to
   `scp` from a sidecar if even that fails.

## Secondary findings

- `resiliency-snapshots` branch push uses `--depth=1` shallow clone + `find
  -mtime +14 -exec rm -rf {}` prune. Not a disk culprit — git working tree
  stays bounded at ~2-3 weeks of PNG panels.
- prometheus `prometheus-data.tar.gz` is ~20-25 MB per topology — bounded by
  the 5h TSDB retention. Not a culprit.
- No panel PNGs in the failed artifacts (Render Dashboard Panels likely
  failed because prometheus wasn't running when the orchestrator crashed).

## Follow-up (not in this commit)

If the host+container trace confirms the Errno-22 traceback storm hypothesis,
the real fix is to either:

1. Set `log_level: info` on the cluster3/5 masters' salt config (the storm is
   only emitted at debug level), or
2. Fix the underlying tornado `on read: [Errno 22]` bug — likely a socket
   that's being read after close on multimaster peer-publisher reconnect.
   The `resetting pusher for reconnect` co-location suggests it's in the
   cluster-peer forward path.
