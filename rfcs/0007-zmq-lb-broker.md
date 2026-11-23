- Feature Name: zmq-lb-broker
- Start Date: 2026-11-23
- RFC PR: (leave this empty)
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

Design for ZeroMQ ReqServer load-balancing broker (supersedes #67215).

Replace the round-robin ZMQ `QUEUE` broker in `salt/transport/zeromq.py`
with the zguide chapter-3 load-balancing broker across both the
non-pooled and pooled `MWorkerQueue` paths, and flip `MWorker` from
`REP` to `REQ`. The result eliminates head-of-line blocking against a
slow MWorker — today a single stuck worker parks every N-th request
behind it and produces `SaltReqTimeout` even while other workers are
idle.

This document captures the target architecture so maintainers can
review the approach before code lands. It supersedes PR #67215 which
is unmergeable as-filed (see "Known blockers" below) and whose author
has been unresponsive for ten months.

# Motivation
[motivation]: #motivation

The `MWorkerQueue` currently proxies `clients -> workers` with
`zmq.device(zmq.QUEUE, self.clients, self.workers)`
(`salt/transport/zeromq.py:567`). `QUEUE` is strict round-robin on the
`DEALER` side: libzmq hands the next incoming request to the next
worker regardless of whether that worker is idle. A single `MWorker`
stuck in a slow handler (large pillar render, external auth, blocked
backend) parks every N-th request behind it in that worker's per-peer
queue while idle workers wait. This is the long-standing head-of-line
/ `SaltReqTimeout` symptom PR #67215 cites. The pooled path
(`zmq_device_pooled`, `:588`) has the same pathology within each pool —
inside a pool, dispatch is still `DEALER` round-robin.

The zguide load-balancing broker pattern avoids this by tracking which
workers are available and dispatching only to idle workers, while
requests queue in the broker instead of per-worker. This eliminates
head-of-line blocking against a slow worker and improves tail latency
under skewed workloads.

# Design
[design]: #detailed-design

## Current architecture

### Non-pooled (`zmq_device`, `salt/transport/zeromq.py:477-586`)

- Frontend `self.clients` is `ROUTER` (`:494`), bound on
  `tcp://interface:ret_port`. Backend `self.workers` is `DEALER`
  (`:518`), bound on the workers IPC/TCP URI.
- Bridge: `zmq.device(zmq.QUEUE, self.clients, self.workers)` (`:567`).
- Context pinned to `zmq.Context(1)` (`:491`); the inline comment at
  `:482-490` documents why — `Context(worker_threads)` caused unbounded
  libzmq message-pool growth (~7-8 MB/min).
- Client options that must survive the rework are documented at
  `:495-516`: `LINGER=1000` (reap one-shot CLI queue slots),
  `ROUTER_HANDOVER=1` (swap stale routing-id on reconnect),
  `TCP_KEEPALIVE{_IDLE=60,_INTVL=15,_CNT=3}` (reap dead peers before
  the 2 h OS default), `IPV4ONLY=0` under `ipv6`, `BACKLOG=zmq_backlog`.
  Worker socket gets `LINGER=1000` (`:519`).
- `mworker_queue_niceness` via `os.nice` (`:521-526`).
  `_start_zmq_monitor()` is attached to `self.clients` at `:517`.
- Teardown at `:574-586` closes sockets before `context.term()`.

### Pooled (`zmq_device_pooled`, `:588-763`)

- Same frontend `ROUTER` with the same options (`:604-623`), plus
  `_set_zmq_heartbeat(self.clients, self.opts)` (`:616`) — comment at
  `:604-612` explains the earlier bug where the pooled path was missing
  heartbeat + keepalive.
- One `DEALER` backend socket **per pool** (`:636`), keyed in
  `self.pool_workers`.
- `salt.master.RequestRouter` (`:662`, defined
  `salt/master.py:1798`) classifies the payload's `cmd` to pick a
  pool; `pool_dealer.send_multipart(msg)` (`:738`) forwards the full
  `ROUTER` envelope.
- Hand-rolled `zmq.Poller` loop at `:691-753`. `DEALER` round-robin
  still governs dispatch within a pool.

### MWorker FSM (`post_fork`, `:871-1011`)

- Socket is `REP` (`:892`) with `LINGER=1`. Either connects to the
  workers URI (`:905`) or binds directly in the `direct_bind` topology
  path (`:900`).
- `request_handler` (`:944-1011`) is a deliberate three-phase lockstep:
  `poll -> recv -> handle -> encode -> send`. Comments at `:947-998`
  spell out why — `REP` FSM deadlocks on any `recv` without a matching
  `send`. Python 3.12 `asyncio.wait_for` cancellation already caused
  that wedge (comment at `:953-958`).
- `handle_message` (`:1013`) wraps `decode_payload` with a
  `SaltDeserializationError` guard; `encode_payload`/`decode_payload`
  (`:1020`, `:1038`) are reused by `forward_message` (`:1078`,
  `:1083`).

## Target architecture

Apply the zguide ch3 LB broker on the broker side; flip workers to
`REQ`.

### Non-pooled broker

- Keep `zmq.Context(1)` (`:491`) and every option at `:495-516`.
  Change only `self.workers`: `DEALER -> ROUTER`. Keep `LINGER=1000`
  (`:519`) — PR #67215 as-filed sets `-1` which would wedge
  `ctx.term()` if any worker dies with a reply buffered; master's
  value wins.
- Replace `zmq.device(zmq.QUEUE, ...)` at `:567` with a `dispatch()`
  method holding broker state: `self.poller`,
  `self.workers_available: list[bytes]`, and optional
  `profile_last`/`profile_interval` counters. Initial poller
  registration covers only `self.workers`; client poll is added on
  first ready frame, removed when `workers_available` goes empty.
- Each `dispatch()` iteration:
  1. Worker frame ready: `message = self.workers.recv_multipart()`,
     structure `[worker_id, b"", client_id_or_empty, ...]`. Append
     `worker_id` to `workers_available`; re-register clients in the
     poller if we had been empty. If `client_id != b""` the frame is
     a reply — forward via
     `self.clients.send_multipart(message[2:])`.
  2. Client frame ready:
     `message = self.clients.recv_multipart()` yields
     `[client_id, b"", payload...]`. Pop head of
     `workers_available`, unregister clients if now empty, then
     `self.workers.send_multipart([worker_id, b""] + message)`.
- Set `ROUTER_MANDATORY=1` on `self.workers` so a send to a vanished
  worker raises `EHOSTUNREACH` synchronously rather than silently
  dropping. Broker catches `EHOSTUNREACH` around the forward-to-worker
  send, drops the `worker_id` from `workers_available`, and either
  requeues or sends an explicit error reply.
- Keep `errno.EINTR` retry (`:568-570`) and the teardown block
  (`:574-586`).

### Pooled broker

- Frontend unchanged (`ROUTER` + full option set at `:604-623`;
  `_set_zmq_heartbeat` at `:616` stays).
- Per-pool backend `DEALER -> ROUTER` (`:636`). `self.pool_workers`
  still keyed by `pool_name` but each value is now a `ROUTER`.
- Add per-pool state
  `self.pool_workers_available: dict[str, list[bytes]]`. The existing
  poller at `:691-694` already registers every pool socket.
- Dispatch loop replaces the body at `:696-753`:
  - Per pool, ready-frame handling is identical to the non-pooled
    case but indexes into `self.pool_workers_available[pool]`. The
    reply-forwarding branch (`:709-712`) is unchanged.
  - Client frame: `salt.payload.loads(msg[2])` ->
    `router.route_request(payload)` (`:725-726`) is unchanged. Then
    pop from `self.pool_workers_available[pool_name]`. If empty,
    buffer on a bounded per-pool deque and temporarily unregister
    the frontend; register again when any pool gets a worker. The
    error-reply branch (`:740-746`) is unchanged.
- Per-pool LB; `RequestRouter` still picks the pool, the broker now
  picks a specific worker in that pool.
- Pool buffering ceiling: `opts.get("zmq_backlog", 1000)` per pool;
  send an explicit "pool saturated" error reply when full so the
  client sees a bounded failure rather than a silent timeout.

### MWorker

- Flip `self._socket = self.context.socket(zmq.REP)` (`:892`) to
  `zmq.REQ`. Keep `LINGER=1` (`:894`) and `_start_zmq_monitor()`
  (`:895`).
- Startup: after `connect()`/`bind()`, send one empty ready frame:
  `await self._socket.send(b"")`. That registers the `REQ` routing-id
  with the broker `ROUTER` and pushes it onto `workers_available`.
- `request_handler` FSM becomes
  `recv_multipart -> handle -> send_multipart(reply) -> send(ready)`
  instead of `poll -> recv -> handle -> send`. The handler **must**
  use `recv_multipart` and index `message[2]` for the payload; a
  plain `recv()` returns only the first frame (`client_id`) and
  `message[-1]` operates on the last byte of `client_id`, not the
  payload. (This is the correctness bug in PR #67215 as-filed; see
  blocker #2 below.)
- Frame format at each hop:
  - Client -> frontend `ROUTER`: payload arrives on the broker side
    as `[client_id, b"", payload...]` after `ROUTER` prepends
    routing-id.
  - Frontend -> worker `ROUTER`:
    `[worker_id, b"", client_id, b"", payload...]`.
  - Worker `REQ.recv_multipart` (`REQ` strips its own identity +
    delimiter): `[client_id, b"", payload...]` delivered to the
    handler.
  - Worker `REQ.send_multipart` reply:
    `[client_id, b"", reply_payload]`. Broker forwards `message[2:]`
    back to frontend.
  - Worker `REQ.send` ready: `[b"", b""]`. Broker only pushes
    `worker_id` onto `workers_available`; no forwarding.

### REQ recovery on broker respawn

`MWorkerQueue` is managed by the process manager and *will* respawn.
After respawn, every worker that was mid-request would otherwise
become permanently silent: `REQ` is in "expecting recv" with its
reply buffered to a vanished peer, so `send(b"")` ready hits `EFSM`
(libzmq `errno=156384763`). Today's `QUEUE+REP` broker degrades
gracefully here — `REP` recovers on the next client request. The
`LB+REQ` design must ship an explicit recovery path:

1. Monitor `ZMQ_EVENT_DISCONNECTED` on `self._socket` at
   `salt/transport/zeromq.py:892` via the existing
   `_start_zmq_monitor()` attachment.
2. On disconnect, close the `REQ` socket and open a fresh one against
   the same URI.
3. Re-send the empty `ready` frame so the new routing-id is picked up
   by the respawned broker.

This is same-change-set work, not a follow-up — without it, broker
respawn produces a correctness regression vs. the current `QUEUE+REP`
design.

## Interactions to preserve

- **Options landed since Feb 2025** — `LINGER=1000`,
  `ROUTER_HANDOVER`, `TCP_KEEPALIVE_*`, `_set_zmq_heartbeat` at
  `:616`, `BACKLOG`, `IPV4ONLY`, `mworker_queue_niceness`,
  context-size=1 (`:491`), and the teardown discipline at `:574-586`
  / `:754-763`. PR #67215 pre-dates every one. The diff must be
  re-applied on top of master, not the other way around.
- **`_start_zmq_monitor`** — attached at `:517 / :624` (clients) and
  `:895` (worker). `ROUTER` and `REQ` both support the monitor; worker
  side now carries load because it drives the respawn-recovery path
  above.
- **`RequestRouter`** at `salt/master.py:1798`, called at
  `salt/transport/zeromq.py:662 / 726`: unchanged. LB is per-pool;
  routing is per-command.
- **`handle_message` / `encode_payload` / `decode_payload`** — PR
  #67215 inlines `salt.payload.loads` into `handle_message`. That is
  **not safe**: `encode_payload` (`:1078`) and `decode_payload`
  (`:1083`) are called by `forward_message` at `:1078,1083`. Keep all
  three methods. (Note: `salt/transport/tcp.py:921` defines a no-op
  passthrough; `salt/transport/ws.py` inlines `salt.payload.loads/dumps`
  at `:634,636` — the symmetry is incomplete but only zeromq's pair
  is load-bearing.)
- **AES rotation / auth path** — the client's routing-id lives in the
  frame, not in broker state, so a worker that rotates keys
  mid-handler just takes longer; the broker holds no per-request
  state. The one risk is queued time exceeding the client-side
  `auth_timeout`; that is saturation, not a broker bug.
- **`master_async_mworker`** (`salt/channel/server.py:1301-1370`,
  `salt/utils/event.py:937-1027`) is orthogonal. The async opt-in
  binds one IPC socket **per worker index** and server-side
  `RequestClient`s connect directly to each worker, bypassing the
  `MWorkerQueue` entirely (`:1331-1348`). The LB-broker rework only
  touches the shared-socket LTS-default path; the two coexist
  unchanged (the choice is made at `pre_fork` time in
  `salt/transport/zeromq.py:836-855`).

## Test plan

New file: `tests/pytests/scenarios/transport/test_zmq_lb_broker.py`.

- **Baseline fairness**: N=5 fast workers, M=200 concurrent echo
  requests. Assert each worker handled ~40 +/- tolerance.
- **Slow-worker head-of-line**: worker 0 sleeps 10 s per request,
  workers 1..4 echo. Fire 50 concurrent 1 s-timeout requests. Assert
  workers 1..4 together served >=48 (today's `QUEUE` broker parks 10
  of the 50 behind worker 0 and they all time out). Headline
  regression.
- **Worker crash mid-request**: 3 workers, send to worker 2,
  `SIGKILL` before reply, client retries. Assert retry served by
  worker 0 or 1 and no stale entry wedges `workers_available` (or
  that it is pruned on the next monitor event). No broker-side hang.
- **Pooled inter-pool isolation**: two pools (`fast`, `maint`), each
  with 2 workers; `maint` workers sleep 10 s. Fire 20 concurrent
  `fast`-classified requests. Assert all 20 complete within 2 s;
  `maint` saturation does not leak.
- **Worker reconnect**: 3 workers, kill worker 1, process manager
  respawns. Assert new worker re-sends `ready` and is dispatched to
  within 5 s.
- **Broker respawn with workers mid-request**: 3 workers, each in a
  10 s sleep handler, kill the `MWorkerQueue` process. Process
  manager respawns it. Assert each worker's `REQ` socket is rebuilt
  via the disconnect-monitor path, re-sends `ready`, and the next
  client request is served.
- **Client disconnect mid-flight**: client fires a request, closes
  its socket before the reply. Broker forwards the reply to a
  vanished frontend routing-id. Assert `workers_available` is not
  wedged (worker returns to pool normally).
- **Unequal-speed fairness beyond 10s/0s**: mix of 100 ms / 10 ms /
  1 ms handlers across workers, 500 concurrent requests. Assert
  throughput is dominated by the fast workers and total time is not
  pinned to the slowest handler.

## Rollout

Phased:

1. Phase 1 (this doc): design.
2. Phase 2: independent correctness review. **Done** — SEND-BACK with
   four blockers captured below; design has been revised to address
   them.
3. Phase 3: implementation.
   - Apply LB broker to non-pooled `zmq_device`. Diff against master
     `zmq_device` — the only intentional deltas should be
     `DEALER -> ROUTER` on `self.workers`,
     `zmq.device(QUEUE, ...)` -> `self.dispatch()`, and the new
     method.
   - Extend LB broker to `zmq_device_pooled`.
   - Flip `MWorker` `REP -> REQ` and rewrite `request_handler`;
     wire `ZMQ_EVENT_DISCONNECTED` to the recovery path.
   - Add tests.
4. Phase 4: changelog, PR for review.

## Alternatives
[alternatives]: #alternatives

- **Keep `QUEUE` and raise `worker_threads`**: scales workers but
  does not fix per-worker head-of-line — a single slow handler still
  parks every N-th request. Operationally observed on sites with
  pillar renders exceeding 10 s.
- **Per-request-type pool sizing** (`zmq_device_pooled` alone):
  helps isolate slow command classes but does not fix intra-pool
  head-of-line, which is the same pathology one level down.
- **Switch to the TCP transport**: solves a different problem; the
  ZeroMQ transport is the LTS default and `SaltReqTimeout` under
  skewed master load is a direct user-visible pain point.

## Unresolved questions
[unresolved]: #unresolved-questions

- Whether the broker should wire `ZMQ_EVENT_DISCONNECTED` on the
  backend `ROUTER` for proactive `workers_available` dedup, or rely
  on `EHOSTUNREACH` from `ROUTER_MANDATORY` on send. Recommendation:
  wire the monitor; covers crash and flaky reconnect without extra
  hot-path state.
- Exact per-pool saturation error payload shape and whether it
  should be a new transport-level error or reuse an existing
  `SaltReqTimeout`-adjacent code.

# Drawbacks
[drawbacks]: #drawbacks

- Replaces a terse `zmq.device(QUEUE, ...)` one-liner with ~100 lines
  of broker-state bookkeeping. The code is well-understood (it is
  the zguide ch3 LB broker pattern verbatim), but it is still more
  surface area than the current design.
- Adds a `REQ` recovery path driven by the ZMQ socket monitor, which
  is new load on a code path that currently has no recovery logic.
- No breaking change for users; the default `worker_threads` /
  `zmq_backlog` knobs retain their meaning. Operators observing
  `SaltReqTimeout` from head-of-line see improvement; no operator
  action is required.

# Known blockers / open items

The following were flagged by independent correctness review and
**must be addressed during implementation**:

1. **Broker respawn is a correctness blocker, not deferrable.**
   `MWorkerQueue` is managed by the process manager and will
   respawn. With the `LB+REQ` FSM, every worker that was mid-request
   becomes permanently silent after respawn: `REQ` is in "expecting
   recv" with its reply buffered to a vanished peer, so `send(b"")`
   ready hits `EFSM` (`errno=156384763`). Today's `QUEUE+REP` broker
   degrades gracefully here — `REP` recovers on the next client
   request. The design must ship the `REQ` recovery path (monitor
   `ZMQ_EVENT_DISCONNECTED` on `self._socket` at
   `salt/transport/zeromq.py:892`, close+rebuild, resend `ready`) in
   the same change set, not as a follow-up.

2. **`request_handler` rewrite is mandatory.** PR #67215 as-filed does
   `request = await self._socket.recv()` (single-frame) then
   `salt.payload.loads(message[-1])`. `recv()` on `REQ` returns only
   the first frame (`client_id`) and `message[-1]` is therefore the
   last byte of `client_id`, not the payload — broken. Replacement
   for the three-phase lockstep at
   `salt/transport/zeromq.py:944-1011` must use `recv_multipart` and
   index `message[2]` for the payload.

3. **`encode_payload` / `decode_payload` must be kept.** PR #67215
   drops them, but they are called by `forward_message` at
   `salt/transport/zeromq.py:1078,1083`. (Note:
   `salt/transport/ws.py` has no such methods — it inlines
   `salt.payload.loads/dumps` at `:634,636`; `salt/transport/tcp.py:921`
   defines a no-op passthrough. Only zeromq's pair is load-bearing;
   the symmetry argument for deletion is wrong.)

4. **Pooled path (`zmq_device_pooled`, landed Aug 2026) must be
   addressed in the same change set.** One slow worker inside a pool
   still head-of-line-blocks that pool. PR #67215 pre-dates
   `zmq_device_pooled` and does not touch it; the design above
   extends the LB broker to the pooled path.
