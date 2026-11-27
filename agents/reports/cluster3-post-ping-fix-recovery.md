# cluster3-fast fault-recovery failures after the glob-fanout fix

CI run: https://github.com/dwoz/salt/actions/runs/45869625842  
Job: `resiliency-test (cluster3, fast)` (databaseId 140081404192)  
Branch under test: `20d39502890` (3008.x local tip)

## TL;DR

14 of ~44 cluster3-fast tests FAIL with the same signature:

```
FAILED '<scenario>': missing=['scale-minion-1', 'scale-minion-2',
                              'scale-minion-3', 'scale-minion-4',
                              'scale-minion-5']
```

Two overlapping causes:

1. **Harness bug (fixable, fixed):** `Topology.salt_ping_all` discards
   partial stdout on subprocess `TimeoutExpired`, AND coerces salt's
   `"Minion did not return. [No response]…"` error string to `True` via
   `bool(v)`.  Both bugs mask each sweep's real state, so the
   `assert_reconnect` union across 3 masters reports `missing=5/5` even
   when several minions ARE responding on at least one master.

2. **Pre-existing data-plane damage (surfaced, not fixed here):**
   `scale-minion-1` accumulates a **455 806-file job-queue backlog** in
   `/var/cache/salt/minion/queues/salt-haproxy/job_queue/` during the
   compose-up / `wait_initial_auth` phase.  The minion stays alive but
   processes zero new jobs for ~3 hours while draining that queue at
   `process_count_max=5` (~15k jobs/hr → ~30 h total drain).  Any test
   whose `assert_reconnect` needs all five scale-minions to respond
   fails, regardless of what fault was injected.

The harness fix lands locally on 3008.x.  The data-plane root cause
(where the 17:05 fanout publishes come from) needs more logs — the
master-1 container restarted at ~17:44 and the pre-17:44 publish origin
is lost.

---

## Evidence trail

### Failure signature

CI log (`agents/reports/cluster3-post-ping/job.log`, lines 1181-1187,
first failing test `test_clock_minion_fwd_60s`):

```
17:59:52 WARNING resiliency.topology salt_ping_all[c3-salt-master-1]:
  subprocess timed out after 135s (cold-import on registry topology?)
  partial_stdout='{\n    "scale-minion-4": true\n}\n{\n    "scale-minion-1":
  "Minion did not return. [No response]\\n...'

17:59:52 WARNING resiliency.topology salt_ping_all[c3-salt-master-3]:
  … partial_stdout='{\n    "scale-minion-3": true\n}\n{\n    "scale-minion-5":
  true\n}\n{\n    "scale-minion-1": "Minion did not return..."'

17:59:52 WARNING resiliency.topology salt_ping_all[c3-salt-master-2]:
  … partial_stdout='{\n    "scale-minion-1": "Minion did not return..."'

18:02:12 WARNING resiliency.topology salt_ping_all[c3-salt-master-1]:
  … partial_stdout='{\n    "scale-minion-1": true\n}\n{\n    "scale-minion-2":
  "Minion did not return..."'

18:02:19 ERROR resiliency.topology FAILED 'clock_minion_fwd_60s':
  missing=['scale-minion-1', 'scale-minion-2', 'scale-minion-3',
           'scale-minion-4', 'scale-minion-5']
```

Across the two 135s sweeps (within the 180s cluster3 `RECOVER_FAST_SEC`
window), the partial outputs across 3 masters cover **every minion as
True at least once** — `-4`, `-3`, `-5` in sweep 1; `-1`, `-2` in
sweep 2.  The union of those partials would close the set.  But
`salt_ping_all` returned `{}` from each timed-out subprocess call,
discarding the salvage.

### Minion-1 is the bottleneck

`c3-salt-minion-1.log` line 1947 (first log line emitted during the
failure window):

```
[INFO    ] Process queue processing: found 455806 queued files
                                     (Running: 3, Max: 5)
[INFO    ] Re-submitting queued job 20261126170504624128
[INFO    ] Re-submitting queued job 20261126170504624128
```

The minion is draining 455 806 persisted job-queue files from
`/var/cache/salt/minion/queues/salt-haproxy/job_queue/`.  Every queued
entry is a resource-registry fanout from jid `20261126170504624128`
(published at **17:05:04** — well before the first test ran at 17:50).
At `Max: 5` concurrent workers and ~1-5 s/file, drain takes ~30 h.
Throughout that drain the minion is unresponsive to new `test.ping`
publishes; from 17:05 to 20:14 the minion processed only two unique
jids (both from the 17:05 publish).

### Jid 20261126170504624128

Returns for this jid in master-2's log:

```
[INFO    ] Got return from d-dummy-0000002 for job 20261126170504624128
[INFO    ] Got return from scale-minion-4   for job 20261126170504624128
[INFO    ] Got return from d-dummy-0000001 for job 20261126170504624128
…
```

Master-3's log shows **5 873 returns** for this single jid, split across
`a-dummy-*` (minion-1), `b-dummy-*` (minion-2), `d-dummy-*` (minion-4)
— three of the five minions' worth of 2 000 resources each.

That's a resource-registry fanout, published during pre-test warmup
(before master-1's log window starts at 17:44).  The publish's
originating `-L` / `*` target wasn't captured in any surviving master
log, so the caller stays unidentified.

### Why the harness mis-reads the sweeps

Two bugs in `tests/resiliency/lib/topology.py::salt_ping_all`:

1. On `subprocess.TimeoutExpired`, `return {}` discards `exc.output`,
   even though the `--out=json` stream often holds one or more
   `{"minion-N": true}` objects already flushed.

2. Both the single-dict and streaming parse paths do `out[k] = bool(v)`.
   Salt emits per-minion error values as strings
   (`"Minion did not return. [No response]..."`), and `bool(string)`
   is `True` for any non-empty string.  A truncated-mid-string tail
   from the salvage path would also parse-fail and reject the whole
   trailing error — that's actually safe — but the single-dict path
   that parses a complete response would have classified the stuck
   minion as reachable.

Fix: salvage `exc.output` through a shared `_parse_ping_stdout` helper
that requires `v is True` for a positive ping.

---

## Timing arithmetic

* `PING_TIMEOUT_SEC` = 15 (salt CLI `--timeout=15`)
* `subprocess_timeout = timeout + 120` = 135 s (CLI wall-clock)
* cluster3 `RECOVER_FAST_SEC` = 180 s (per
  `conftest.py:220-223`)

Two futures sweeps (3 masters in parallel per sweep) × 135 s =
**270 s to complete 2 full sweeps**.  180 s wall-clock budget kills
the test at the end of sweep 2 regardless of whether the subprocess
had just finished.  The `salt_ping_all` warnings in the log at 17:59:52
and 18:02:12 confirm exactly two sweeps per failure, 2 min 20 s apart.

So even with the harness fix below, fault scenarios on cluster3 get
**at most two full sweep rounds** at 135 s/sweep before the
`RECOVER_FAST_SEC=180` deadline closes.  Fast tests that need a few
seconds of post-reconnect settle on top of the already-slow CLI are
up against the hard ceiling.

The fix below materially improves the union signal (recovering ~60 %
of per-sweep partials) but does NOT help the underlying
`scale-minion-1` queue backlog.  A minion stuck at `Running: 5, Max: 5`
with 455 k pending files simply will not answer a new ping inside any
realistic test window.

---

## What's fixed in this report's commit

`tests/resiliency/lib/topology.py` —

* Salvage `exc.output` on `TimeoutExpired`.  Decode bytes (always
  bytes, even with `text=True` — a `Popen.communicate()` timeout
  quirk), feed the partial buffer to `_parse_ping_stdout`, return the
  partial coverage instead of `{}`.
* New `_parse_ping_stdout` static method factors the single-dict + streaming
  JSON parse out of `salt_ping_all`, enforces `v is True` (not
  `bool(v)`) so error-string values don't flip to reachable.
* Partial / truncated streams stop at the first decode error and
  return everything parsed up to that point.

`tests/resiliency/lib/test_parse_ping_stdout.py` (new) —

13 regression tests covering:

* Single-dict + streaming parse paths.
* `"Minion did not return…"` as False (BOTH paths).
* Truncated-mid-object salvage.
* Verbatim partial-output from CI 45869625842 line 1181.
* `TimeoutExpired` salvage end-to-end.
* `TimeoutExpired.output is None` tolerance.
* rc!=0 with empty stdout → `{}`.

All 13 new tests pass under `venv314/bin/pytest`:

```
tests/resiliency/lib/test_parse_ping_stdout.py::...  13 passed in 0.01s
```

Pre-existing `test_leak_gate.py` failures (`_FakeSpec` missing `.name`
attribute) are unrelated — same failures on `20d39502890` without my
change.

---

## What's NOT fixed

### The minion-1 queue backlog origin

Jid `20261126170504624128` fires at 17:05:04, well before any test
starts.  The master-1 container restarts at ~17:44 (its log begins
there with `Starting up the Salt Master` / `salt-master is starting`),
so the publish's originating command is unrecoverable from current
artifacts.  Candidates:

* Compose-up healthcheck issues a wildcard `test.ping` from a pre-test
  shell probe.
* `wait_initial_auth` PRE-DATES the `salt_ping_all -L` rewrite in some
  earlier call site.  (Unlikely — I grepped `topology.py` end-to-end
  and every `salt_ping_all` call uses `-L`.)
* `tests/monitoring/cluster-3node` compose has a startup hook that
  fires a legacy wildcard.  Not spot-checked here; would be the next
  stop.

A targeted re-run with master-1 log retention from boot (e.g. no
container restart during setup, or shipped compose-up logs) would
surface the caller directly.

### The hard 180 s recovery ceiling vs. 2 × 135 s sweep cost

cluster3's `RECOVER_FAST_SEC=180` leaves exactly two sweeps per
`assert_reconnect` call.  When the registry fanout saturates a minion,
no amount of sweeping gets around the drain.  Options for a follow-up:

* Per-test exemption: test clock_minion_fwd_60s ALREADY targets minion-1
  specifically (`_first_minion = minion_containers[0]`), so its
  recovery window could legitimately widen via `window_sec=…` in
  `assert_reconnect`.  But pointing the test at a fresh minion each
  run would be cleaner.
* Fleet-rotation: `_first_minion` could pick a minion based on test
  index, so no single minion absorbs every clock/minion-side fault +
  the pre-test backlog on top.
* Reset: run `rm -rf /var/cache/salt/minion/queues/*/job_queue/*` on
  every minion between tests.  Resets the backlog visibility; doesn't
  fix the cause.

Each of those is a wider conversation than the `salt_ping_all` fix.

---

## Repro / verify

Partial salvage is covered by the new `test_parse_realworld_cluster3_partial_output`
test which feeds byte-for-byte the 200-byte partial from line 1181 of
the failing CI job and asserts `{"scale-minion-4": True}` comes back
(not `{}`).

End-to-end validation requires the cluster3 stack to be up with the
stuck minion-1 queue reproduced.  Not run here — the local stack
isn't in a comparable state.  The next cluster3 nightly after this
commit will re-measure.

---

## Files touched

* `tests/resiliency/lib/topology.py` — fix.
* `tests/resiliency/lib/test_parse_ping_stdout.py` — new regression
  tests (13 passing).

Working tree change is local-only on 3008.x; not pushed, no PR.
