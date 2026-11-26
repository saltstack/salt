# mm-failover: test_saltop_kill_job_mid_flight JID detection failure

- **CI run**: dwoz/salt 45718582847, job `resiliency-test (multimaster-failover, fast)` (job id 139570886893)
- **Verdict**: test-infra bug — not a salt-core regression
- **Fix location**: `tests/resiliency/test_salt_ops.py` (plus regression test at `tests/pytests/unit/resiliency/test_salt_ops_jid_parse.py`)
- **Branch**: 3008.x (local commit, not pushed per standing directive)

## Failure signature

```
FAILED test_salt_ops.py::test_saltop_kill_job_mid_flight -
  Failed: saltop_kill_job_mid_flight: could not determine state.sleep JID
  (neither --async output nor jobs.list_jobs returned one)
```

Reproduces on `multimaster-failover` only; passes on single / mm-hothot / syndic / cluster3 / cluster5 (although cluster5 may also be latently exposed — see "Secondary at-risk topologies" below).

## Root cause (two interacting bugs)

### Bug 1: `_parse_async_jid` was never actually parsing `--async` output

The helper tried `json.loads(stdout)` on output from `salt --async --out=json '*' state.sleep 60`. But `salt --async` **ignores** `--out=json`:

- `salt/cli/salt.py:171-174` — the `--async` branch unconditionally does
  `salt.utils.stringutils.print_cli(f"Executed command with job ID: {jid}")`
  before `--out` is consulted. The output is literal text, never JSON.

Consequence: `_parse_async_jid` returned `""` on every topology. On single/hothot/cluster3 the test still passed because the **fallback** `_scrape_recent_state_sleep_jid(topology, primary)` ran against the primary master, which held the jid in its job cache. mm-failover broke that fallback too (bug 2).

### Bug 2: primary master is not the master the minion is attached to on failover

On `multimaster-failover`:
- `tests/resiliency/compose/multimaster/minion-failover.conf` sets `master_type: failover` + `master_shuffle: True`, so the minion attaches to ONE peer picked at startup.
- `topology.spec.primary_master = "mm-salt-master-a"`, but `master_shuffle` often lands on `mm-salt-master-b`. The CI log confirms every neighboring test recorded `RECOVERED ... via mm-salt-master-b`.

With no connected minion matching `*` on master-a:
- `salt/client/__init__.py:_check_pub_data` sees empty `pub_data["minions"]`, prints `"No minions matched the target. No command was sent, no jid was assigned."`, and returns `{}` from `cmd_async`.
- `salt.py:171-174` then prints `"Executed command with job ID: 0"`. No jid is published and no entry lands in master-a's job cache.
- `jobs.list_jobs` on master-a therefore has no recent `state.sleep` → fallback scrape returns `""` → `pytest.fail`.

mm-hothot avoids this because both masters are hot (minion attached to both). Single/syndic have only one master, so primary is always right. cluster5 is also `master_type: failover` but passed in this run — likely luck (`master_shuffle` happened to seat the minion on the primary); treat it as at-risk.

## Fix

Three changes in `tests/resiliency/test_salt_ops.py`:

1. **`_parse_async_jid` rewritten to match plain text**: regex over stdout lines for `job ID:\s*(\S+)`, rejecting `0` as "no jid" (the no-minions-matched sentinel). No json.loads anywhere.

2. **New helper `_dispatch_state_sleep_jid(topology, masters)`**: iterates the master list, dispatches `salt --async '*' state.sleep 60` on each, returns `(jid, master)` for the first peer whose publish succeeded. Lets single/hothot keep their primary-first dispatch (no behavioral change on topologies that already worked) while covering failover topologies.

3. **`test_saltop_kill_job_mid_flight` uses the helper + iterates the scrape fallback across all masters**, and sends `saltutil.kill_job` through the same master that produced the jid (so the minion sees the kill for a job it's actually running). `notes=` records `killed_jid={jid} via_master={m}` for post-hoc attribution.

Master-iteration order: primary first, then remaining peers — preserves ordering determinism on topologies where any master works, falls through only when necessary.

Scenario preserved: still publishes `state.sleep 60`, still sleeps `KILL_JOB_WAIT_SEC` (default 15s), still issues `saltutil.kill_job <jid>`, still spot-checks test.ping — i.e. still exercises "kill a long-running job mid-flight", just on the right master.

## Regression tests

`tests/pytests/unit/resiliency/test_salt_ops_jid_parse.py` imports the resiliency module directly (no docker fixtures) and pins:

- `_parse_async_jid` plain-text parse works; `"job ID: 0"` → `""`; empty / unrelated stdout → `""`; **json-shaped stdout with a `jid` field → `""`** (guards against the old buggy behavior being reintroduced).
- `_dispatch_state_sleep_jid`: primary-first short-circuits when master-a works (no-op on single/hothot), falls through to master-b when master-a returns `jid=0` (the mm-failover scenario), returns `("", "")` when every master is empty, skips a master that raises during `exec`.

10 tests, all pass locally on `venv314/bin/python -m pytest`.

## Secondary at-risk topologies

- **cluster5** is also `master_type: failover` + `master_shuffle: True`. It passed this run but could flake the same way. The fix also covers it transparently — no behavior change needed there, just better coverage.
- **`test_saltop_pillar_refresh_during_state`** uses the same `_parse_async_jid(primary)` pattern but doesn't `pytest.fail` on empty jid (it just skips the drain poll). On mm-failover its drain-check invariant is silently bypassed. Out of scope for this fix but worth tracking — add to a follow-up if we want stricter semantics.

## Files touched

- `tests/resiliency/test_salt_ops.py` — `_parse_async_jid` rewritten, `_dispatch_state_sleep_jid` added, `test_saltop_kill_job_mid_flight` iterates masters and routes kill via the dispatch master.
- `tests/pytests/unit/resiliency/test_salt_ops_jid_parse.py` — new file, 10 regression tests covering both bugs.

## What I did NOT do

- No changes under `salt/*` — this is test-infra only, matching the directive.
- Did not push, did not open a PR.
- Did not spin up the full mm-failover compose locally — the unit tests exercise the exact helpers, the CI log already shows which master the minion is on, and the bug chain is traceable statically through salt CLI + client source. The next CI run on 3008.x will confirm.
