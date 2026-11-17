# Cluster-peer forward-pusher warning flood (Errno 22 cascade)

## Observed symptom

On a 5-master cluster running the resiliency test suite (artifact
`resiliency-cluster5-43824366115`, 4.9 h duration), each master's container
log accumulates:

| Marker                                                                       | Count (master-3) |
|------------------------------------------------------------------------------|------------------|
| `Unable to forward event to cluster peer <peer>; resetting pusher for reconnect` | 369,676 |
| `error on read: [Errno 22] Invalid argument`                                 | 368,679 |
| `Exception in callback ... send_aes_key_event ... StreamClosedError`         | 368,662 |

The log volume on cluster3 (debug-level) fills /var/lib/docker and
ENOSPCes the GHA runner's own `_diag` log.

## Root cause

Two coupled issues in `salt/channel/server.py:MasterPubServerChannel.publish_payload`
(current line 5173 on 3008.x).

### Issue 1 — unnamed task for non-`cluster/peer` fan-out (minor, correctness)

Line 5284 (pre-fix):

```python
tasks.append(asyncio.create_task(pusher.publish(event_data)))
```

The task has no `name=`, so when `task.result()` raises `StreamClosedError`
and the handler reaches:

```python
peer = task.get_name()
...
for pusher in self.pushers:
    if pusher.pull_host == peer and pusher.pub_sock is not None:
        ...
```

`task.get_name()` returns an auto-assigned `Task-NNNN`, which never matches
any `pusher.pull_host`. The log line still fires with a confusing
`"cluster peer Task-NNNN"` payload and the `pub_sock` reset is a no-op.

Impact: accounts for roughly 0.1% of the observed warnings on master-3
(a handful of distinct `Task-NNNN` entries vs. 184k entries each for
`salt-master-1` and `salt-master-2`). The loud path is Issue 2.

### Issue 2 — no per-peer rate limit on the warning or on `send_aes_key_event` reschedule (dominant)

The dominant warnings cite proper peer names (`salt-master-1`,
`salt-master-2`), meaning the `pub_sock` reset path *does* execute. The
peer simply remains unreachable (node clock-skewed, SIGSTOPed, or network
disconnected per the resiliency scenarios), so every subsequent event
through `publish_payload` re-executes:

1. `log.warning("Unable to forward event to cluster peer %s; ...", peer)`
2. `self.io_loop.call_later(2.0, self.send_aes_key_event)`

At ~10 events/sec per dead peer that is ~20 warnings/sec and ~20
scheduled `send_aes_key_event` calls per second per peer, each of which
in turn fires `event.fire_event` on the local IPC bus. When the local
EventPublisher's inbound stream churns under this load, tornado's
`IOStream._handle_read` can observe the fd in a half-closed state and
emits:

    [WARNING ] error on read: [Errno 22] Invalid argument

from `tornado.iostream` (gen_log). Each failing `send_aes_key_event`
also produces a `[ERROR ... Exception in callback ...
StreamClosedError`] traceback.

The EINVAL warning is a **symptom** of the amplification, not a
cause. The fix is to debounce the per-peer failure handling so that
a persistently-down peer produces O(1) warnings per cool-off window,
not O(events) warnings.

## Design

Minimal change, scoped to `MasterPubServerChannel`:

- Add `self._peer_reset_times: dict[str, float]` populated at `__init__`
  (`{}`).
- Add constant `_PEER_RESET_COOLDOWN = 10.0` seconds. Chosen because:
  - `send_aes_key_event` is already scheduled 2 s after a reset.
  - A real transient (network re-converge, Raft election, SIGCONT) is
    resolved in well under 10 s.
  - At 10 s a steady-state dead peer emits ~1 warning/10 s, i.e. a 100x
    reduction at 10 events/sec, which matches the observed ~369k/scenario
    log entries dropping to ~3.7k.
- In the `StreamClosedError` branch:
  - Compare `now - self._peer_reset_times.get(peer, 0)` against the
    cool-off.
  - If still within cool-off: downgrade the warning to `log.debug` and
    skip the `call_later` reschedule. The `pub_sock` reset still runs
    (idempotent — a `None` pub_sock remains `None`) because a fresh
    reset after a reconnection must not be silently swallowed.
  - If outside cool-off: emit the warning at WARNING, schedule
    `send_aes_key_event`, and record `_peer_reset_times[peer] = now`.
- Name the fan-out task at line 5284 with `name=pusher.pull_host` so the
  `peer` string is always a real peer name, not an auto-generated
  `Task-NNNN`. Issue 1 fix.

### Why not a lock or cancellation?

The task prompt flagged three possible classes of fix:

1. socket-state race (atomic cleanup)
2. tornado reading a dead fd (convert OSError(EINVAL) → StreamClosedError)
3. reconnect storm (backoff on `send_aes_key_event`)

The artifact evidence rules out (1) and (2) as causes:

- The `pub_sock` reset path *is* idempotent and re-entrant-safe
  (`pub_sock = None` guarded by `if pusher.pub_sock is not None`).
  There is no concurrent-publish race left to close — the issue is
  that a down peer produces an unbounded series of *sequential*
  failures, not a window of concurrent ones.
- The `[Errno 22]` warning comes from tornado's own `IOStream`
  internals on the **local IPC bus** stream, not on the cluster-peer
  pusher. Converting EINVAL to StreamClosedError in Salt code has no
  attachment point here — the warning originates in the
  `tornado.iostream` module.

(3) is the correct class of fix. The chosen cool-off window of 10 s is a
balance point; it is a `salt.channel.server` module constant rather than
an opt, because the forward-pusher warning rate is not an operator
tuning dial.

### Why not touch `send_aes_key_event` itself?

Each call creates a fresh local-bus `SaltEvent` via `get_master_event`
and tears it down. The underlying failure (`fire_event` →
`pub_sock.send` → `stream.write` on a closed stream) comes from the
local IPC bus being saturated during the flood — removing the flood
removes the cascade, without mutating consensus-adjacent code.

## Safety analysis

- **No consensus / Raft / mmap change.** Fix is 100% in
  `MasterPubServerChannel.publish_payload` + two init attrs.
- **Preserves StreamClosedError semantics.** The `except
  tornado.iostream.StreamClosedError` block still runs, still resets
  `pub_sock` on every failure (not just the first), still logs the local
  IPC failure. Only the WARNING level and the `call_later` reschedule
  are rate-gated.
- **Preserves AES-key re-announcement for real reconnects.** First
  failure after a quiet period schedules the key event normally. A
  burst of 1,000 failures in 1 s still schedules it exactly once.
- **Idempotent on re-entry.** `_peer_reset_times` is a plain dict keyed
  on peer name; no cross-task coordination, no lock, no cancellation of
  in-flight work.
- **No behavior change on healthy clusters.** Peer healthy →
  StreamClosedError never fires → the new state is unused.

## Scope statement (explicit)

Per task constraints:

- No refactor of the surrounding `tasks = []; for pusher ...` loop.
- No change to the `except tornado.iostream.StreamClosedError:` catch
  type or its outer `except Exception` fallback.
- No change to the `call_later(2.0, self.send_aes_key_event)` delay
  value beyond adding the per-peer debounce gate.
- No change to the mmap registry or Raft service.
- No cross-cluster / Paxos surface touched.

## Unit test

`tests/pytests/unit/channel/test_cluster_forward_pusher.py`:

1. Build a `MasterPubServerChannel` with mocked `opts`, `transport`,
   `pushers`.
2. Install two mock pushers, one of which raises `StreamClosedError`
   on `publish`.
3. Invoke `publish_payload` in rapid succession (10 events).
4. Assert:
   - First failure logs at `WARNING` and schedules `send_aes_key_event`.
   - Subsequent failures within 10 s log at `DEBUG` and **do not**
     schedule `send_aes_key_event`.
   - `pub_sock` reset path still runs each time (no regression).
   - Task 5284 is created with the peer name, not `Task-NNNN`.

## Expected impact

Pre-fix: ~369k WARNINGs + ~369k EINVAL + ~369k send_aes_key_event
tracebacks per cluster5 run.

Post-fix (projected, for same scenarios): ~3.7k WARNINGs + ~0 EINVAL
(no local-bus flood to trip tornado's `_handle_read`) + ~3.7k
send_aes_key_event invocations (one per 10 s window per down peer).
Peer reconnect latency is unchanged: still 2 s after the first failure.
