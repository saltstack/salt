# Marathon-outage deadline misses on SINGLE topology (CI run 43773954141)

## Signature

On run `43773954141` (SHA `9b4b3a716ce`), single-topology, three
`test_master_marathon.py` tests failed with every minion missing after
the recovery window expired:

| test                     | fd_delta | rss_delta_kb | missing      |
|--------------------------|----------|--------------|--------------|
| `marathon_outage_30m`    |   -8898  |    27640     | all 3        |
| `marathon_outage_60m`    |    +52   |    64744     | all 3        |
| `marathon_outage_120m`   |    +6    |    28520     | all 3        |

Preceded earlier in the run (same CI worker, same containers) by:

| test                                   | fd_delta | rss_delta_kb | missing |
|----------------------------------------|----------|--------------|---------|
| `orch_random_kill_one_process_tree`    |  +2446   |   44196      | all 3   |

Same-run `cluster5` topology was **CLEAN** on every marathon test:

| test                        | reconnect |
|-----------------------------|-----------|
| `marathon_outage_30m`       |   29 s    |
| `marathon_outage_60m`       |   28 s    |
| `marathon_outage_120m`      |   29 s    |

So the regression is **single-topology-specific**: when there is only
one master and `orch_random_kill` has already SIGKILLed a subtree of
the master, every subsequent marathon test runs on a degraded master
that never recovers the minions.

## Local 3-min outage repro: CLEAN

On `dwoz/resiliency-test-suite@7f34367d0c8`, local single-topology,
with `docker stop -t 30 rs-single-salt-master; sleep 180; docker start`:

* All 3 minions answered `test.ping` at t+7 s after master restart.
* Per-minion fd stable at 44 before and after (no accumulation).
* Per-minion RSS delta ~40 KB (noise).
* Master total fd 830 → 889 (+59 across all salt-master processes --
  warming workers; well under per-minion thresholds).
* Minion-1 log shows the clean recovery path:
  1. `salt.transport.zeromq Request timed out while waiting for a response. reconnecting.`
  2. `DNS lookup or connection check of 'salt-master' failed.`
  3. `Master hostname: 'salt-master' not found or not responsive. Retrying in 30 seconds`
  4. `[salt.minion:5404] Re-initialising subsystems for new master salt-master`
  5. `[salt.minion:5425] Minion is ready to receive requests!`
  6. First `test.ping` answered.

So the marathon code path on master-restart is fundamentally working
at 3-min scale, matching the cluster5 CI observation.

## What's different on single-topology CI

### Ordering: orch_random_kill runs BEFORE marathon

Test file order is `test_fileserver_orch.py` then `test_master_marathon.py`.
On single topology, `orch_random_kill` picks a random non-MainProcess
`salt-master` subprocess (MWorker, Maintenance, EventMonitor,
FileserverUpdate, etc.) and SIGKILLs it, then sleeps `SHORT_FAULT_SEC`
(= `TIER_FIRSTMISS_SEC` = 35 s) before `assert_reconnect`.

`fd_delta=+2446` for this test is the key signal. With 3 minions and
per-minion fd steady at ~44 pre-fault, +2446 across the fleet (~800
fds per minion) is the signature of either:

* The master respawning the killed subprocess entered a tight-loop
  retry that held many sockets open per minion.
* The minions themselves forked many short-lived return-channel
  children that didn't settle before the AFTER sample.
* Every minion's PID changed between BEFORE and AFTER (`sample_container`
  tracks MinionProcessManager / MainProcess), so the fd counts
  compare different process trees.

### Hypothesis: sample_container pid aliasing after minion crash

`lib/topology.py::_minion_main_pid` resolves pid via
``pgrep -f 'salt-minion.*MinionProcessManager'``. If a minion crashes
and restarts (e.g., the master-side kill triggered an upstream race
that OOMed a minion), the NEW pid is picked up for AFTER sampling.
The new process tree carries its own fd set (~800 fds counted against
the empty BEFORE baseline). This would produce exactly the
+2446-across-3-minions signature we see.

### Why marathon then fails

If the orch_random_kill failure left the master in a degraded state
(crashed worker, held listening sockets in TIME_WAIT, pid-tracking
desync), the subsequent marathon stop/start sequence would stop a
partially-wedged master and bring it back without the minions' auth
state ever recovering.

Marathon fd_delta=-8898 on the 30m test is consistent with minions
dying across the outage (minion pid gone → `_minion_main_pid` returns
empty → `sample_container` returns `(0, 0)` → delta = -BEFORE).

## Suspect salt/ code paths (unverified - need CI artifact drill-down)

Not reproducible locally at 3-min outage; need to either:

1. Reproduce at 30-min scale locally (in progress; see
   `agents/scratch/marathon_10min.sh` and `.log`).
2. Pull the uploaded CI minion/master logs for run `43773954141`,
   single topology job 132995852498, and look for:
   * `salt/crypt.py::AsyncAuth._authenticate` `InvalidStateError` -
     the `#70772` family. Would be the ur-signature.
   * `salt/minion.py::_send_req_sync` stuck in `SaltReqTimeoutError`
     retry loop with no progress.
   * `salt/transport/zeromq.py` socket wedge after long disconnect
     (never raises, never retries).
   * Master-side: `salt/master.py::MWorker` spawning a replacement
     subprocess after the SIGKILL and holding onto old sockets until
     the container is restarted.

## Harness-side mitigations already landed

* `76eaf5b364b` pause workload across AFTER-sample settle (handles
  workload-driven noise in `rss_kb_per_min` on recovered scenarios).
* `256d01db487` multimaster pubkey shard (addresses a different auth
  race -- multimaster, not single).
* `c11bb935cd9` results.jsonl stash fix (no more silent drops).
* `e404b796801` 2 s settle before AFTER sample (kills the fork-pair
  spike noise floor).

## Recommended next steps

1. **Harness-side (this change)**: port
   `test_baseline_workload_only`'s internal slope check to use the
   same compound gate as `assert_reconnect` -- slope alone is not a
   leak signature, the test's stricter `rss_per_min >
   RSS_LEAK_KB_PER_MIN` check was failing legitimate workload-driven
   working-set growth even when fd and bulk-RSS were clean.
2. **CI artifact drill-down**: pull
   `resiliency-single-logs-43773954141.tar.gz` (uploaded by the
   `Collect Logs on Failure` step) and inspect
   `rs-single-salt-master.log` around 23:44:34 (orch_random_kill
   fault) and 00:25:13 (marathon_outage_30m fault) for the specific
   salt-side exception trace.
3. **Isolation test**: on single topology, run marathon tests
   WITHOUT running orch_random_kill first (deselect via
   `-k 'not random_kill'`). If marathon then passes, the regression
   is proven to be a cross-test contamination bug in
   `orch_random_kill`, not a marathon-code issue.
4. **Consider ordering guard**: resiliency suite currently relies on
   file-order; destructive single-master tests that leave the master
   non-functional should either be isolated to their own job matrix
   cell or restart the master cleanly before yielding to the next
   test. Precedent: `3a593f52eaf` revives master after OOM squeeze
   on single topology.
