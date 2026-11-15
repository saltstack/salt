# resource_oom_squeeze cascade fix

## Observed in local repro (single topology)

Compose stack: `tests/resiliency/compose/single` brought up with
`PROM_HOST_PORT=19094 CADVISOR_HOST_PORT=18083 docker compose -p resiliency-single up -d`
(image `resiliency-single-salt:latest` present; no `--build` needed).

Steady-state baseline:
- all 3 minions auth'd, `salt '*' test.ping` returns True x 3 within ~3s
- `rs-single-salt-master` contains tini (pid 1) + salt-master MainProcess (pid 7)
  + EventPublisher, PubServerChannel, EventMonitor, Maintenance, BatchManager,
  ReqServer + MWorkerQueue + 10 x MWorker-default workers.
- Host-side `HostConfig.Memory`=0, `MemorySwap`=0 (unlimited).

Fault injection:
```
docker update --memory=200m --memory-swap=200m rs-single-salt-master
```
Exit code 0. Within ~15s:
- Host `journalctl -k` shows repeated
  `Memory cgroup out of memory: Killed process <pid> (...)` with
  `oom_memcg=/system.slice/docker-<cid>.scope`.
- Processes killed include MWorker-default-*, EventPublisher, ReqServer, and
  eventually enough of the MainProcess tree that tini (pid 1) exits.
- `docker inspect rs-single-salt-master` -> `Status=exited ExitCode=137
  OOMKilled=false`. ExitCode 137 == 128 + SIGKILL; OOMKilled=false because
  the top-level cgroup task that triggers the flag was not the direct kill
  target - tini itself eventually terminates after its children are reaped.

Relax step as written in the test:
```
docker update --memory=2g --memory-swap=-1 rs-single-salt-master
```
rc=0, BUT: the container is still `exited`. `docker exec` returns:

> Error response from daemon: container <id> is not running

This is the exact cascade:
- `test_resource_oom_squeeze` loses minion visibility (fds drop as minions
  can't reach the dead master; `assert_reconnect` fails with "3/3 minion(s)
  did not answer test.ping within 180s").
- Every subsequent test that uses the master (test.ping sweeps, `salt`
  invocations) fails the same way.
- Tests that `docker exec rs-single-salt-master <cmd>` directly
  (saltop_key_reject, saltop_cache_corruption, saltop_kill_job_mid_flight)
  fail with non-zero rc because the container is not running.

Confirmed recovery path: `docker start rs-single-salt-master` -> container
runs tini + salt-master again -> minions re-auth within ~45s -> fleet pings
return True x 3.

## Chosen fix: option B (restart master container after relax)

The resiliency semantic the suite advertises is: "fleet recovers after
fault clears". An OOM-kill of the whole salt-master process tree is a
legitimate fault - a real deployment would see its supervisor (systemd,
k8s, etc.) restart salt-master. The compose entrypoint is tini + a single
`salt-master -l info` command with no restart policy, so there is no
supervisor; the test must perform the restart itself to simulate
recovery.

Why not option A (bump the memory ceiling to 300MB)?
- Fragile: a working-set that just fits today is only pressure that OOMs
  tomorrow. We'd be tuning the number per environment/workload.
- Weaker signal: the squeeze that doesn't OOM-kill anything doesn't
  exercise the fault we care about.

Why not option D (--memory-reservation soft limit)?
- The soft limit only kicks under host pressure, which the CI runner
  never exerts. The test would effectively become a no-op.

Why not option C (full compose restart as teardown)?
- Way heavier than needed: minions, prometheus, cadvisor are all fine.
  Only the master container exited.
- Would also delay all downstream tests by the full compose-up window
  (~60s) when a single `docker start` recovers in ~5s + ~45s auth.

Option B: after the relax `docker update`, inspect whether the master
container is still running. If not, `docker start` it. Let
`assert_reconnect`'s existing 180s window absorb the re-auth time (the
auth path was already covered by the initial fixture `wait_initial_auth`;
this is the same wait, triggered mid-session).

Follow-on: when the container was revived, the minions re-establish a
fresh zmq context against a fresh master pid, which legitimately grows
their fd count + RSS even though no leak is occurring. The
`assert_reconnect` leak gate (`rss_per_min > RSS_LEAK_KB_PER_MIN AND
(fd_delta > 0 OR rss_delta > LEAK_BULK_RSS_KB)`) sees that as a
`fd_accumulation` signal. To preserve the leak gate's meaning on
non-revived runs (cluster3, cluster5) while not false-positiving on
single, we call `wait_initial_auth` after the revive and resample
`before` fresh. The leak check then measures only the
post-revive-steady-state deltas, which stay near zero.

## Tests affected

Only `test_resource_oom_squeeze` changes. Downstream tests (resource_cpu
_throttle, resource_write_amplify, saltop_*) benefit transitively because
the master container is up again when they start, but their code is
untouched.

The `OOM_RELAX_MEMORY` and `OOM_HOLD_SEC` env knobs are preserved.
`notes=` string in the JSONL row is extended to flag whether a container
restart was needed, so the analyzer can distinguish "squeeze killed the
container" (expected on single + small memory limits) from "squeeze was
survivable" (expected on cluster3/cluster5 where the per-master working
set is smaller).
