# NSX Salt Minion Return-Path Resource Runaway

## Summary

On the `dwozniak-91-ss` / VCF 9.2 Nimbus test environment, the NSX Salt minion
stopped responding to `salt "*" test.ping` after the Salt master was restarted
several times while testing Salt 3008 master PKI changes. The missing minion was:

```text
d043a916-43e6-4523-a352-b6b1187e85a5 -> mgmt-nsx-01.vcf.nimbus.internal
```

The appliance was reachable over the network and SSH, but `salt-minion.service`
on NSX had failed due to a cgroup OOM kill:

```text
Active: failed (Result: oom-kill)
MemoryMax=209715200
```

Raising the minion's systemd memory limit from `200M` to `300M` and restarting
the minion restored connectivity. After the restart, all five accepted minion
keys returned `True` to `test.ping`.

The memory limit was not the whole story. The log pattern before the OOM shows
the minion stuck for hours in repeated return-channel and event-dispatch timeout
paths. That behavior looks like an error-path resource runaway: return retries,
event publishing, reconnects, and/or minion child processes are not cleaning up
fast enough under master backpressure or master instability.

## Environment

Observed environment:

```text
Testbed: dwozniak-91-ss-mgmt-anchor
VSP gateway: 10.162.38.32
VSP k8s node used for access: 25.0.0.109 / vsp-platform-tn5f2
NSX appliance: mgmt-nsx-01.vcf.nimbus.internal
NSX IPs: 25.0.0.31, 25.0.0.32
NSX OS: Ubuntu 24.04
NSX kernel: 6.6.116-nn3-generic
Salt minion: 3008.0rc4
Python: 3.14.5
```

Salt master state at the time this was diagnosed:

```text
salt-master pod: 1/1 Running
master id: salt-master
master keys: /etc/salt/pki/master/salt-master.pem and salt-master.pub
SYS_ADMIN: absent
bind mount hack: absent
```

The other accepted minions were responding:

```text
53614d0c-50c9-4227-80cc-64ec83ac652c -> in-cluster salt-minion pod
97d8c55f-d9fc-4a0d-be88-8a2e8f568125 -> mgmt-vc.vcf.nimbus.internal
c0862b8f-1842-4834-8d23-7c6c0d8f7b8b -> sddc-manager.vcf.nimbus.internal
d54044f1-b322-46fc-acb7-d7b63356fe74 -> ops.vcf.nimbus.internal
```

## What Failed

The Salt master had NSX's key accepted, but NSX did not answer:

```text
Accepted Keys:
53614d0c-50c9-4227-80cc-64ec83ac652c
97d8c55f-d9fc-4a0d-be88-8a2e8f568125
c0862b8f-1842-4834-8d23-7c6c0d8f7b8b
d043a916-43e6-4523-a352-b6b1187e85a5
d54044f1-b322-46fc-acb7-d7b63356fe74

d043a916-43e6-4523-a352-b6b1187e85a5:
    Minion did not return. [No response]
```

NSX itself was alive:

```text
25.0.0.32 mgmt-nsx-01.vcf.nimbus.internal
ping: ok
tcp/22: open
tcp/443: open
```

Root SSH worked, and the Salt package was installed:

```text
/usr/bin/salt-minion
/usr/bin/salt-call
Python 3.14.5
salt-minion 3008.0rc4 (Argon)

ii  salt-common  3008.0~rc4  amd64
ii  salt-minion  3008.0~rc4  amd64
ii  vcf-salt-ext 1.0.0.0     all
```

The local minion service was failed:

```text
salt-minion.service - The Salt Minion
Active: failed (Result: oom-kill) since Wed 2026-05-20 08:50:58 UTC
Main PID: 1987091 (code=exited, status=0/SUCCESS)
Memory: 200.0M memory peak
```

## Memory Limit Evidence

There were two systemd memory-limit sources on the appliance.

The static drop-in configured by the Salt pre-run script was `300M`:

```text
/etc/systemd/system/salt-minion.service.d/10-limits.conf

[Service]
CPUQuota=50%
MemoryMax=300M
```

The active limit was lower because systemd had a runtime control override:

```text
/etc/systemd/system.control/salt-minion.service.d/50-MemoryMax.conf

# This is a drop-in unit file extension, created via "systemctl set-property"
# or an equivalent operation. Do not edit.
[Service]
MemoryMax=209715200
```

`209715200` bytes is exactly `200M`. This file is created by
`systemctl set-property`, not by directly editing the static unit file.

The static pre-run script on NSX explicitly chooses `300M` for the small/medium
form factor:

```text
/opt/saltstack/salt_minion_pre_run_config.sh

# Configure salt-minion memory limit based on form factor
# SMALL (4 vCPUs) and MEDIUM (6 vCPUs) form factors use 300M, LARGE and XTRA LARGE use 400M
if [ "$NUM_VCPUS" -le 6 ]; then
  MEMORY_MAX=300M
else
  MEMORY_MAX=400M
fi

# Update systemd service override file with memory limit
...
MemoryMax=$MEMORY_MAX
```

The likely writer for the runtime control override is the VCF Salt extension
minion config API:

```text
/opt/saltstack/vcf-salt/minion_utils.py

MEMORY_LIMIT_MB = 'memory_limit_mb'
MAX_MEMORY_USAGE = 'MemoryMax'

...

elif cfg_key == MEMORY_LIMIT_MB:
    return self.__update_service_property(
        MAX_MEMORY_USAGE, cfg_key, str(config[cfg_key]), "M"
    )

...

systemctl set-property salt-minion.service MemoryMax=<value>M
```

The VCF Salt extension log confirms the appliance reported `200` until we
changed it:

```text
2026-05-02 01:22:09 - run_salt_api - INFO - Running the update_minion_config of SaltMinionConfigUtil in minion_utils
2026-05-02 01:42:09 - API_EXECUTION_RESULT: ... "memory_limit_mb": 200, "cpu_limit_pct": 50
...
2026-05-20 08:47:03 - API_EXECUTION_RESULT: ... "memory_limit_mb": 200, "cpu_limit_pct": 50
```

After setting the property to `300M`, later status reports changed to:

```text
2026-05-21 00:07:36 - API_EXECUTION_RESULT: ... "memory_limit_mb": 300, "cpu_limit_pct": 50
```

This means `200M` was not an NSX product service limit discovered in an NSX
unit or script. It was the active Salt minion desired-state/runtime property.

## OOM Timeline

Before the OOM, the NSX minion repeatedly logged return and event failures:

```text
May 20 06:01:19 mgmt-nsx-01 salt-minion[1987236]:
  [ERROR] Request timed out while waiting for a response. reconnecting.

May 20 06:21:52 mgmt-nsx-01 salt-minion[1987236]:
  [WARNING] Unable to register resources with master: Message timed out

May 20 06:22:00 mgmt-nsx-01 salt-minion[1987236]:
  [ERROR] Timeout encountered while sending {'cmd': '_return',
  'id': 'd043a916-43e6-4523-a352-b6b1187e85a5',
  'jid': '20260520062128367949',
  'fun': 'saltutil.refresh_grains', ...}

May 20 06:22:03 mgmt-nsx-01 salt-minion[4155645]:
  [WARNING] The minion failed to return the job information for job 20260520062128367949.
  This is often due to the master being shut down or overloaded.
```

The timeout pattern continued for hours:

```text
[ERROR] Error dispatching event. Message timed out
[ERROR] Request timed out while waiting for a response. reconnecting.
```

The cgroup OOM happened at the configured `200M` limit:

```text
May 20 08:50:57 mgmt-nsx-01 kernel:
  /opt/saltstack/ invoked oom-killer: gfp_mask=0xcc0(GFP_KERNEL), order=0, oom_score_adj=0

May 20 08:50:57 mgmt-nsx-01 kernel:
  memory: usage 203312kB, limit 204800kB, failcnt 8587

May 20 08:50:57 mgmt-nsx-01 kernel:
  Memory cgroup stats for /system.slice/salt-minion.service:

May 20 08:50:57 mgmt-nsx-01 kernel:
  Memory cgroup out of memory: Killed process 1987236 (/opt/saltstack/)
  total-vm:793768kB, anon-rss:74784kB, file-rss:8704kB, shmem-rss:0kB,
  UID:986 pgtables:728kB oom_score_adj:0

May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Failed with result 'oom-kill'.

May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Unit process 326319 (/opt/saltstack/) remains running after unit stopped.
May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Unit process 326320 (/opt/saltstack/) remains running after unit stopped.
May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Unit process 326352 (/opt/saltstack/) remains running after unit stopped.
May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Unit process 326460 (/opt/saltstack/) remains running after unit stopped.
May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Unit process 326461 (/opt/saltstack/) remains running after unit stopped.

May 20 08:50:58 mgmt-nsx-01 systemd[1]:
  salt-minion.service: Consumed 1h 2min 7.868s CPU time, 200.0M memory peak, 0B memory swap peak.
```

The child processes remaining after the unit stopped are important. They suggest
that the service and/or minion child process tree did not cleanly tear down
after the main process was killed.

## Immediate Mitigation Applied

The service was repaired by raising the active runtime property to `300M` and
restarting the minion:

```text
systemctl set-property salt-minion.service MemoryMax=300M
systemctl reset-failed salt-minion.service
systemctl restart salt-minion.service
```

After restart:

```text
Active: active (running)
Main PID: 2501437 (python3.14)
Memory: 95.0M (max: 300.0M available: 204.9M peak: 105.1M)
MemoryMax=314572800
```

Salt verification succeeded:

```text
d043a916-43e6-4523-a352-b6b1187e85a5:
    True

full salt "*" test.ping:
    all 5 accepted minions returned True
```

The `300M` limit should be treated as mitigation only. The interesting bug is
that the minion reached `200M` during prolonged return/event timeout handling.

## Code Paths That Match the Log Pattern

### 1. ZMQ request/return path

The production symptom:

```text
Request timed out while waiting for a response. reconnecting.
```

comes from `salt/transport/zeromq.py` in `RequestClient._send_recv`:

```python
if isinstance(exc, SaltReqTimeoutError):
    log.error("Request timed out while waiting for a response. reconnecting.")
...
if not self._closing:
    await self._reconnect()
send_recv_running = False
```

Relevant properties of this path:

- Return payloads are queued into a single `RequestClient._queue`.
- A timeout sets an exception on the future.
- `_send_recv` reconnects the shared socket after timeout.
- Under master backpressure, many return futures can time out while queued.
- Reconnect storms can happen if the master is slow, restarting, or overloaded.

In the 3008.x source tree, `RequestClient._send_recv` still has this short
circuit:

```python
if future.done():
    continue
```

That line was already patched on the live NSX appliance when inspected:

```python
if future.done():
    break
```

So the NSX OOM was not caused by the *unpatched* `future.done(): continue`
version of that exact bug. However, it is still the same return-path pressure
area. The minion was spending hours in timeout/reconnect behavior from this
code path.

### 2. Return retry / job return path

The production symptom:

```text
The minion failed to return the job information for job ...
This is often due to the master being shut down or overloaded.
```

matches minion return retry behavior around:

```python
return await self.req_channel.send(
    load, timeout=timeout, tries=self.opts["return_retry_tries"]
)
```

and retry timing from:

```python
def _return_retry_timer(self, max=False):
    ...
    random_retry = random.randint(
        self.opts["return_retry_timer"], self.opts["return_retry_timer_max"]
    )
```

On NSX, the minion config included retry tuning:

```yaml
return_retry_timer: 30
return_retry_timer_max: 60
return_retry_tries: 5
request_channel_timeout: 60
request_channel_tries: 5
```

This means each failed return can keep retrying for a non-trivial amount of
time, and many concurrent failed returns can overlap.

### 3. Minion event dispatch path

The production symptom:

```text
Error dispatching event. Message timed out
```

matches `MultiMinion.handle_event`:

```python
async def handle_event(self, package):
    try:
        await asyncio.gather(*[_.handle_event(package) for _ in self.minions])
    except Exception as exc:
        log.error("Error dispatching event. %s", exc)
```

On NSX the error repeated continuously alongside request reconnects. If
`handle_event` calls overlap or retain timed-out tasks/resources, that can
become a resource growth path.

### 4. Event publisher async cleanup

NSX also logged:

```text
/opt/saltstack/salt/lib/python3.14/site-packages/salt/utils/asynchronous.py:156:
RuntimeWarning: coroutine 'BaseEventLoop.shutdown_asyncgens' was never awaited

/opt/saltstack/salt/lib/python3.14/site-packages/salt/utils/asynchronous.py:163:
RuntimeWarning: coroutine 'BaseEventLoop.shutdown_default_executor' was never awaited
```

The warnings point at `salt/utils/asynchronous.py`:

```python
self.asyncio_loop.run_until_complete(
    self.asyncio_loop.shutdown_asyncgens()
)
...
self.asyncio_loop.run_until_complete(
    self.asyncio_loop.shutdown_default_executor()
)
```

Those warnings do not prove a leak by themselves, but they are consistent with
async cleanup not completing cleanly under the error condition.

### 5. Event publish task accumulation

`salt/utils/event.py` creates publish tasks when not running in sync mode:

```python
task = self.io_loop.create_task(self.pusher.publish(msg))
self._publish_tasks.append(task)
```

The inspected snippet does not show immediate pruning of `_publish_tasks` in
the same method. If the pusher is timing out or publish tasks are retained after
completion/failure, repeated `Error dispatching event. Message timed out` could
grow memory over time. This is a concrete investigation target.

### 6. Child process lifecycle

The minion service uses:

```text
KillMode=process
```

This means systemd kills only the main process for normal stop operations, not
the whole control group. After the OOM, systemd reported several child
`/opt/saltstack/` processes still running. If job return subprocesses are
waiting on return retries when the main minion dies, `KillMode=process` can
leave them alive.

This may not be the root leak, but it worsens recovery and can make the unit's
memory/process state misleading after failure.

## Relationship To The Known Transport Bug

A separate bisect showed that Salt 3008.x drops queued return messages under
master backpressure because `RequestClient._send_recv` skips messages whose
future timed out before reaching the wire:

```python
if future.done():
    continue
```

In a harness with delayed master ACKs, that caused 3008 to drop many more
frames than 3007. Changing the short-circuit to not skip the message restored
delivery in the harness.

The live NSX appliance already had the patched `break` form when inspected, so
the NSX OOM is likely not the exact same bug. It is likely adjacent:

- the master was slow/restarting/overloaded during testing,
- the minion entered the return timeout/reconnect path repeatedly,
- return retries and event dispatch errors overlapped for hours,
- memory grew to the active cgroup cap,
- the main minion process was OOM-killed,
- child processes remained after the unit stopped.

The key point is that the patched transport fixed one delivery loss mode, but
there may still be a resource cleanup/runaway problem when returns and events
time out for a long period.

## Hypotheses To Validate

1. **Return retry overlap leaks process or memory**
   - Many concurrent job returns time out while the master is restarting or slow.
   - Each return keeps retrying for up to `return_retry_tries`.
   - Worker processes remain alive while waiting for return retries.
   - Memory grows with the number of overlapping return attempts.

2. **Event publish tasks are retained**
   - `event.fire_event()` creates publish tasks and appends them to
     `_publish_tasks`.
   - Publish failures/timeouts may not remove completed tasks promptly.
   - Repeated `Error dispatching event. Message timed out` grows the task list.

3. **Reconnect path creates replacement `_send_recv` tasks/sockets faster than
   old ones are cleaned**
   - `_send_recv` reconnects on `SaltReqTimeoutError`.
   - Reconnects under constant timeout could create churn in sockets/tasks.
   - Cleanup may lag or fail under Python 3.14 async shutdown warnings.

4. **`KillMode=process` leaves child processes behind**
   - OOM kills the main process.
   - Systemd does not kill the full cgroup.
   - Child return processes keep running and logging after unit failure.
   - Recovery requires explicit restart/reset or a stronger kill mode.

5. **The `200M` limit made the failure easy to hit**
   - Current normal running memory after restart was about `95M`.
   - During the error loop the service reached `200M`.
   - A higher cap masks the symptom but does not prove healthy cleanup.

## Suggested Reproduction

Use either a real NSX minion or a smaller harness that exercises Salt's
`RequestClient` and minion return path:

1. Start a Salt 3008 minion with:
   - `MemoryMax=200M`
   - `process_count_max` low enough to make process growth visible
   - `return_retry_timer=30`
   - `return_retry_timer_max=60`
   - `return_retry_tries=5`

2. Apply the known transport delivery fix so the test is not just reproducing
   the `future.done(): continue` message-drop bug.

3. Impair master return ACKs:
   - restart the master repeatedly,
   - block port `4506`,
   - or delay the master's return ACK path with a fake master or slow
     `_return/store_job` path.

4. Launch concurrent minion jobs that return data.

5. Monitor:
   - total RSS for the minion service cgroup,
   - number of minion child processes,
   - number of asyncio tasks if instrumented,
   - `RequestClient._queue` depth if instrumented,
   - event publish task list length if instrumented,
   - ZMQ socket/reconnect count.

Useful commands on a live appliance:

```bash
systemctl show salt-minion -p MemoryCurrent -p MemoryPeak -p MemoryMax
systemd-cgls /system.slice/salt-minion.service
ps -o pid,ppid,rss,vsz,etime,cmd -C python3.14
journalctl -u salt-minion -f
```

Expected confirmation signal:

- master backpressure starts,
- timeout/reconnect messages begin,
- child process count or retained async task count grows,
- RSS climbs monotonically or fails to return to baseline,
- OOM occurs around the configured cgroup cap.

## Potential Fix Directions

These are investigation directions, not proven fixes:

1. Ensure timed-out return futures are cleaned without retaining payloads,
   callbacks, sockets, or tasks.
2. Add pruning for completed/failed event publish tasks in `salt.utils.event`.
3. Rate-limit or coalesce reconnect attempts from the shared return
   `RequestClient`.
4. Bound concurrent return retries per minion.
5. Make return retry failure paths explicitly close/destroy channels.
6. Revisit `KillMode=process` for the minion service; `control-group` may be a
   safer failure recovery mode if child processes can outlive the main minion.
7. Add regression tests that simulate master ACK backpressure and assert stable
   task/process counts, not just delivery count.

## Current Status

As of the last live check:

```text
NSX salt-minion: active (running)
MemoryMax: 300M
NSX test.ping: True
full salt "*" test.ping: all 5 minions True
```

The environment is healthy, but the evidence should be treated as a real bug
candidate: a prolonged transport/return/event error condition can drive the
NSX minion beyond a 200M cgroup limit and leave child processes behind after
the main process is killed.
