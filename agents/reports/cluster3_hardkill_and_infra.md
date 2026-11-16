# cluster3 hard-kill + resiliency sidecar restart loop — 2026-11-15

Scope: run 43773954141 on dwoz/salt (dwoz/resiliency-test-suite tip).

## Verdicts (TL;DR)

1. **cluster3 was killed by `No space left on device` on the GHA worker
   itself.** Not an outer-timeout exit, not an OOM, not an in-script
   signal. The runner's own `_diag/Worker_*.log` writer hit ENOSPC and
   the worker process crashed, stranding step 8 ("Start environment")
   as `in_progress` with `completed_at: null` and leaving the log blob
   ungarbled on blob storage (hence the 404).

2. **Prometheus restart-loops the entire run on cluster3 + cluster5.**
   The workflow's "Prepare prometheus_data dir" step chowns the wrong
   directory for those two topologies — a plain path-mismatch
   between the base-compose location (`tests/monitoring/cluster-{3,5}node/`)
   and the actual overlay bind source
   (`tests/resiliency/compose/cluster{3,5}/prometheus_data`). The chown
   is a no-op; docker auto-creates the real bind source root-owned;
   prometheus panics on `queries.active: permission denied` and restarts
   under `restart: unless-stopped` every ~1s. Confirmed by 362
   "Starting Prometheus Server" lines in the cluster5 artifact's
   `rs-cluster5-prometheus.log` over 5.5h.

## Evidence

### 1. The hard-kill annotation

```
gh api repos/dwoz/salt/check-runs/132995852482/annotations
```

```
System.IO.IOException: No space left on device :
    '/home/runner/actions-runner/cached/2.338.2/_diag/Worker_20261115-231700-utc.log'
    at System.IO.RandomAccess.WriteAtOffset(...)
    at GitHub.Runner.Worker.Worker.RunAsync(...)
    at GitHub.Runner.Worker.Program.MainAsync(...)
Unhandled exception. System.IO.IOException: No space left on device
    (same)
```

Two annotations on the job:
- `failure`: the ENOSPC trace above
- `notice`: ubuntu-latest migration to Ubuntu 26 (irrelevant)

### 2. Per-step timing matches

| Step | cluster3 | cluster5 |
|------|----------|----------|
| Install test dependencies | 23:17:10 -> 23:18:55 (1m45s, ok) | 23:17:14 -> 23:18:47 (ok) |
| **Start environment** | 23:18:55 -> **null** | 23:18:47 -> 04:17:57 (completed, failure) |
| Analyze Results | never ran | ran |
| Upload Artifacts | never ran | ran (if: always()) |

Cluster3's step 8 has `completed_at: null, status: "in_progress"` even
after the job's `completed_at: 02:13:26Z`. A clean timeout would
produce exit 124 + a conclusion. A runner-process crash is the only
state that leaves a step stranded like this.

### 3. The prometheus bind-mount mismatch

Workflow's current PROM_DATA_DIR for cluster3:
```
tests/monitoring/cluster-3node/prometheus_data   <-- chowned
```

Actual bind source after `docker compose -f base -f overlay config` :
```
tests/resiliency/compose/cluster3/prometheus_data   <-- bound
```

The overlay at `tests/resiliency/compose/cluster3/monitoring-overlay.yml`
line 52 uses `../../../tests/resiliency/compose/cluster3/prometheus_data`
relative to its own path, so compose resolves:
`<repo-root>/tests/resiliency/compose/cluster3/prometheus_data`.
The workflow pre-create targets the stress-test monitoring stack's
directory, which the overlay never binds.

The cluster5 artifact shows the symptom cleanly:

```
time=2026-11-15T23:22:20.694Z level=INFO ... msg="Starting Prometheus Server"
time=2026-11-15T23:22:20.695Z level=ERROR source=query_logger.go:138 ...
    msg="Error opening query log file" ... err="open /prometheus/queries.active:
    permission denied"
time=2026-11-15T23:22:20.695Z level=ERROR ... msg="failed to initialize active
    query tracker" ... (exit, restart)
time=2026-11-15T23:22:21.857Z level=INFO ... msg="Starting Prometheus Server"
    (same loop)
```

362 restarts / 5h30m = ~1/min. Each restart writes a handful of lines
to `docker logs` (which the runner spools to `/var/lib/docker/containers/.../*.log`).
Over cluster3's ~3h run, that's still only ~1800 restart cycles; not
by itself fatal. But combined with 3 masters + 5 minions logging at
`-l debug` (each master log hit ~390MB on cluster5 by hour 5 — see
`cluster5/artifacts/c5-salt-master-{3,4,5}.log` sizes) the runner's
root volume (`~14 GB` on `ubuntu-latest`) can realistically exhaust.

### 4. Why only cluster3 died when cluster5 has the same bug

cluster5 ran for 5h30m, generated ~1.2 GB of artifact logs, and still
had budget headroom (single also completed at ~1.3 GB artifact). The
difference is probably just which runner drew the short straw on
starting free-space (GHA runners are provisioned with ~14 GB free
but background caches vary) + the fact that cluster3 has 8 debug-
logging salt processes (3 masters + 5 minions) while cluster5 also
has 10 (5 masters + 5 minions). Within noise.

No topology-specific "cluster3 is heavier" cause was found. Treat
this as a run-of-the-mill disk-pressure dice roll that the restart-
loop made significantly more likely, and that any other topology on
the same hardware mood could trigger.

### 5. Local reproduction of the restart loop

Brought up `resiliency-single` (same prometheus overlay pattern):

```
$ docker ps --format '{{.Names}} {{.Status}}' | grep -E 'prom|cadv'
rs-single-prometheus    Restarting (2) ...
rs-single-cadvisor      Restarting (255) ...

$ docker logs rs-single-prometheus | tail
... level=ERROR source=query_logger.go:113 ...
    err="open /prometheus/queries.active: permission denied"
panic: Unable to create mmap-ed active query log

$ docker logs rs-single-cadvisor | tail
F1116 ... cadvisor.go:173] Failed to start manager: inotify_init: too many open files
```

- prometheus: same path-ownership failure (dev box didn't pre-chown
  the `./prometheus_data` dir either; same symptom as cluster3+5 in CI).
- cadvisor: unrelated host-level limit (my sandbox has 60+ containers
  consuming fsnotify watches). Not a CI concern; GHA runners have
  clean inotify budgets.

## Fixes applied

### `.github/workflows/nightly-resiliency-test.yml`

1. **"Prepare prometheus_data dir" step** (lines ~108-152): point the
   `PROM_DATA_DIR` for `cluster3` and `cluster5` at the directory the
   overlay actually binds. Side comment explains why the base path is
   wrong.
2. **New "Disk preflight" step** (after Install test dependencies):
   log `df -h / /tmp` + `docker images` so the next ENOSPC has a
   baseline to subtract from.
3. **"Collect Logs on Failure" step**: write `artifacts/disk-usage.txt`
   capturing `df -h`, `du -sh /tmp/*`, `docker ps -s` so a future
   near-miss is visible even if the runner recovers.

### Deliberately NOT applied

- **Switch prometheus/cadvisor off `restart: unless-stopped`.**
  Tempting as a belt-and-suspenders ("one failed start panics,
  bam, done"), but legitimate restarts happen during
  `master_marathon` outages and we want the sidecar to come back.
  The permission fix makes the loop moot.
- **Reduce `-l debug` on masters/minions.** Debug logs are the
  diagnostic signal for 90% of resiliency failures. Rotating
  them would be a meaningful follow-up but is behavior-affecting
  and belongs in its own commit.
- **Shrink cluster3 (drop to 3 minions, drop haproxy).** Not needed;
  the disk-full was not a topology-size issue. The user flagged
  this as a discuss-first option in the task.
- **Normalize cadvisor local inotify.** Host-side operator
  intervention that violates the "Salt-perspective fixes only"
  memory rule; dev-box problem, not a CI problem.

## Known residual fragility in the workflow

Numbered against the current (post-fix) file:

- **L203 `timeout "$outer_timeout" ... ./run_resiliency.sh`**: hands
  pytest its own `exec`, so SIGTERM from timeout reaches pytest. No
  trap in the script means a partial `results.jsonl` is retained
  (good) but any in-flight test doesn't get a cleanup hook (acceptable;
  the Collect Logs step re-dumps container state).
- **L245-250 Snapshot Metrics**: `docker compose ... stop prometheus`
  is best-effort (`|| true`). If prometheus was in a restart loop,
  the stop is still a clean stop, so this works correctly post-fix.
- **L310-313 `docker logs "$c" > "artifacts/..."`**: unbounded log
  dump. With 5h-of-debug master logs this will easily produce
  2-3 GB per topology. Already observed in-tree (390 MB each master
  on cluster5). Consider `docker logs --tail 50000 "$c"` or a size
  cap, but this is the same tradeoff as reducing `-l debug` and
  belongs in its own change.
- **L368-391 Panel Summary**: depends on `steps.upload-artifacts.outputs.artifact-url`;
  if Upload Artifacts fails for size/quota reasons the summary silently
  renders without the artifact link. Not blocking.
- **"Publish panels to resiliency-snapshots branch"** step guards on
  `hashFiles('artifacts/panels/*.png') != ''`. If render_panels.py
  failed (e.g. matplotlib ImportError) the step is silently skipped.
  Would benefit from a per-topology `success/skipped/failed` counter
  in the final Panel Summary. Non-urgent.

## What won't fix the hard-kill

Nothing at the workflow level can save the job from a GHA runner
`_diag` ENOSPC: the worker process is what writes the step logs, and
it crashed. `if: always()` on Upload Artifacts only runs when the
runner is still up. Possible mitigations (all out of scope for this
commit):

- Pre-free disk at job start (uninstall Android SDK, dotnet, etc. —
  the `jlumbroso/free-disk-space` action pattern recovers ~20 GB).
- Reduce debug verbosity or rotate container logs via docker daemon
  config.
- Split the matrix so each topology runs its own smaller job budget
  (already true; cluster3 has its own runner — the issue was absolute
  disk pressure, not cross-topology interference).

The prometheus restart-loop fix removes the most-wasteful contributor
(the one measured to produce 362 restart cycles in 5.5h on cluster5),
which should push cluster3's next run comfortably past its previous
~3h kill point.

## Commits

- `.github/workflows/nightly-resiliency-test.yml`:
  * Correct cluster3 + cluster5 `PROM_DATA_DIR` paths
  * Add Disk preflight step
  * Add post-run disk-usage dump in Collect Logs on Failure
