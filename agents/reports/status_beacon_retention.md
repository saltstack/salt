# Status beacon retains ~2 MB/min on minion, not released after removal

## Summary

Running the `status` beacon at `interval: 1` on a Salt minion causes the
minion's `MinionProcessManager` process to grow its RSS by **~2 MB per
minute** of beacon runtime. Memory is retained past beacon cleanup:
after removing the beacon config and refreshing beacons, the growth
does not release within a +120 s drain window.

Retention is in a steady state ~2 MB/min after transient allocator
behavior settles, so this is retention of long-lived refs (or C-level
buffers holding references), not a working-set spike that drains.

## Versions

- Salt: `v3008.x` HEAD (`e54d4826db0`), editable install into
  minion container
- Python: `3.10.20`
- Platform: Linux (ubuntu-based container, kernel 6.19.14)
- Topology: single-master (1 master, 3 minions), no multi-master,
  no cluster, no syndic

Reproduced on single-master, multimaster-hothot, and syndic topologies
in the resiliency CI run on branch `dwoz/resiliency-test-suite`
(commit `e54d4826db0`, GHA run 45497893297):
- single-fast: `rss_delta_kb=14644` fleet-sum over 3 minions
- mm-hothot-fast: `rss_delta_kb=6564` over 1 minion
- syndic-fast: `rss_delta_kb=6016` over 2 minions

Per-minion retention scales linearly with beacon runtime, not with
minion count.

## Reproduction

The resiliency suite's `tests/resiliency/test_salt_ops.py::test_saltop_beacon_flood`
test exercises the exact path:

1. Write to one minion's `/etc/salt/minion.d/beacon-flood.conf`:
   ```yaml
   beacons:
     status:
       - interval: 1
   ```
2. On the master, `salt <minion_id> saltutil.refresh_beacons`.
3. Hold `TIER_STANDARD_SEC` (~30 s). During this window, the status
   beacon fires once per second and emits `loadavg` / `cpustats` /
   `meminfo` / `vmstats` / `time` data.
4. Delete the beacon config file from the minion.
5. `saltutil.refresh_beacons` again (should unload the beacon).
6. Wait +120 s for Python / C allocator pressure to drain.
7. Sample the minion's `MinionProcessManager` RSS.

Expected: RSS returns to within noise of baseline after step 5–6.
Actual: RSS remains ~2 MB/min above baseline (sustained across the
+120 s reprobe window), so the retention is not a transient.

## Measurement instrumentation

The resiliency suite's leak gate compares a baseline sample
(`tests/resiliency/lib/topology.py::sample_minions`) against a
post-fault sample, sums `VmRSS` from `/proc/<pid>/status` of the
minion's `MinionProcessManager` child, and computes a minute-normalised
slope. A reprobe at +120 s after the initial trip distinguishes
transient drain (pass) from sustained retention (fail).

For `saltop_beacon_flood` on single-fast locally (post-fix, `topology.py`
reprobe enabled):

```
LEAK candidate after 0s via rs-single-salt-master (11351 KB/min,
  reason=bulk_rss_retention); re-sampling at +120s
LEAK after +120s reprobe: 2160 KB/min > 200 KB/min
  (fd_delta=-10 rss_delta_kb=7596)
```

The transient post-beacon spike (~11 MB/min short window) drains
substantially but leaves 2160 KB/min sustained growth at the +120 s
reprobe.

## Scope / not-a-cause

The status beacon's `beacon()` function itself allocates a fresh `ret`
dict per invocation and holds no module-level state (`salt/beacons/status.py`).
The downstream status execution module functions (`loadavg`, `cpustats`,
`meminfo`, `vmstats`, `time`) also read from `/proc/*` and return fresh
dicts without caches. The retention is downstream of these — somewhere
in the beacon dispatch, event emit, or loader lifecycle.

Candidate retention sites (not yet proven):
- Minion-side event buffer for emitted beacon events
- `salt.beacons.Beacon` / `salt.loader.beacons` not fully releasing
  the beacon's module + its bound `__salt__` closure on
  `saltutil.refresh_beacons` removal
- `__salt__` lazy-loader cache retaining `status.*` module references
  after the beacon stops calling them

## Impact

- Any minion running a status (or similar) beacon at short intervals
  accumulates RSS at a rate proportional to the beacon fire rate.
- Removing the beacon via `saltutil.refresh_beacons` does not reclaim
  the retained memory.
- Not immediately fatal but produces monotonic minion RSS growth on
  long-running fleets where beacon configs are added and removed
  dynamically.

## Suggested investigation path

1. Instrument a minion with `tracemalloc.start(25)` around a 30-call
   status-beacon cycle to narrow the retention site (filtering out
   loader-import paths and small-object allocator noise).
2. Inspect the beacon-emit path in `salt/minion.py` /
   `salt/beacons/__init__.py` for retained event payloads or callback
   closures.
3. Compare behavior with `saltutil.refresh_beacons` vs a minion
   restart — if a restart fully reclaims the RSS but
   `refresh_beacons` does not, the leak is in the refresh-time
   teardown of the beacon loader, not in the beacon dispatch itself.

## Workaround for CI

The resiliency suite catches this via its leak-gate reprobe. Until
the retention is fixed, `test_saltop_beacon_flood` is a legitimate
failure on single-fast / syndic-fast / multimaster-hothot-fast.
Two options:

- Mark the test `pytest.xfail(reason="beacon dispatch retention —
  see this issue")` while the underlying salt bug is open.
- Leave the test red as a trip-wire so a future fix removes the
  retention signal and the test flips to pass without needing any
  test-side change.
