# Raft Consensus for Salt Master Cluster — Planning Notes

Working notes captured from planning discussion. Living document; revise as
decisions land.

## Goal

Replace shared-FS coordination in Salt's master cluster with Raft-managed
cluster state. Phase 1 covers cluster membership only. Long-term, multiple
Raft logs may manage different aspects independently.

Bulk data (keys, minion blobs) continues to flow over the existing peer
event channel; the Raft log carries metadata only.

## Existing state (consensus branch / master)

### Cluster config
- `salt/config/__init__.py:201-228` — `cluster_id`, `cluster_peers`,
  `cluster_pki_dir`, `cluster_pool_port` (4520),
  `cluster_key_pass`
- `salt/config/__init__.py:1754-1757` — defaults
- `salt/config/__init__.py:4246-4263` — validation

### Hot-spots that branch on cluster mode
- `salt/master.py:204` — `populate_secrets()` creates shared `cluster_aes`
- `salt/master.py:253-256` — routes `pki_dir` to `cluster_pki_dir`
- `salt/master.py:401-419` — dropfile-based leader election for key rotation
  (first Raft replacement target)
- `salt/master.py:422-425` — `rotate_cluster_secret()`
- `salt/master.py:941-943` — peer notification on startup
- `salt/channel/server.py:136-138, 459-460, 507-510` — channel paths use
  `cluster_aes` and `cluster_pki_dir`
- `salt/channel/server.py:1730-1891` — pool-publish to peers, TCPPuller on
  `cluster_pool_port`, `handle_pool_publish` dispatch

### Shared-FS assumptions today
- `cluster_pki_dir`: `peers/{master_id}.pub`, `.aes`, `cluster`/`cluster.pub`,
  `minions/{minion_id}`
- `cachedir`: `.dfn` dropfile, `sessions/{minion}`

### Inter-master link
Publish-only TCPPuller on `cluster_pool_port`. No req/reply transport between
masters. Targeted messaging is achieved at the application layer via per-peer
pushers indexed by `peer_id` (e.g. autojoin's `join` → `join-reply`).

### Existing tests
- `tests/pytests/integration/cluster/conftest.py` — multi-master fixture
- `tests/pytests/integration/cluster/test_basic_cluster.py`
- `tests/pytests/scenarios/cluster/test_cluster.py`

## What auto_scale (sibling branch, almost stable) provides

Branch: `auto_scale_clean_v2`. Diverges from same merge base as `consensus`
(`2addbd9c5e2`). Do **not** rebase consensus onto auto_scale yet.

Useful pieces already implemented there:
- Authenticated peer channel with signed messages + token replay protection
- `cluster_secret` bootstrap for new master joins
- Join protocol: discover → cluster pub → encrypted secret → cluster/peer
  keys → `join-notify`
- Per-peer pushers in `MasterPubServerChannel.pushers` (peer_id → pusher);
  this is the directed-messaging mechanism we'll reuse
- In-memory `PrivateKeyString` / `PublicKeyString` in `salt/crypt.py`
- `PoolRoutingChannel` is master↔minion (port 4506), not master↔master

When auto_scale lands, the autojoin handler will be retargeted to propose
`AddLearner` through the Raft leader rather than broadcasting peer state
directly.

## Source: rift (~/src/raft)

Never released. Strategy: poach modules + tests into Salt tree under Apache
2.0 with headers noting origin. No external rift dependency.

### Poach into `salt/cluster/consensus/raft/` (or `salt/cluster/consensus/raft.py`)

Prefer a `raft/` subpackage for the multi-file poach (`node.py`, `log.py`, …);
use a single `raft.py` only if we deliberately collapse the surface later.

- `node.py` (~948 L) — `Node`, `Peer`, `ManualPeer`, `Candidacy`,
  `NodeState`, `Vote`
- `log.py` (~858 L) — `LogEntry`, `LogEntryType`,
  `LogEntryCommitStatus`, `Log`, `BaseStorage`, `JSONStorage`,
  `BaseStateMachine`. Drop `LMDBStorage` and `MsgPackStorage` for now.
- `scheduler.py` (~159 L) — interface + `ManualTimeoutScheduler`. Drop
  threaded scheduler.
- `util.py` (~94 L)
- `chaos.py` (~119 L) — fault injection helpers, used by tests

Skipped: `runtime.py` (we use Salt transport), `flatbuffers_serializer.py`,
`async_runtime.py`, `mvcc.py`, `native_log.pyx`, `native_state.pyx`,
`serialization.py` (use `salt.payload` msgpack instead).

Approximate poached surface: ~2.1k lines.

### Poach tests into `tests/pytests/unit/cluster/consensus/raft/`
- `test_node.py`, `test_node_safety.py`
- `test_log.py`
- `test_scheduler.py`
- `test_chaos.py`
- `test_exactly_once.py` (keeps shape green even though we don't use client
  sessions in P1)

Skipped: `test_proto_ser.py`, `test_lmdb_storage.py`, `test_rust_mvcc.py`,
`test_runtime.py`.

`ManualPeer` and `ManualTimeoutScheduler` are I/O-free, so the unit tests
port cleanly and lock in algorithm correctness before any transport work.

### Rift features to keep
- Pre-vote (`pre_request_vote`) — avoids disruptive elections on flaps
- `Peer.voting` flag — natural fit for "Raft learners" requirement
- `LogEntryType.CONFIG` — distinguishes membership entries from commands
- `client_id` / `sequence_num` on `LogEntry` — keep the shape even if
  unused in P1; adding later would be a migration

### Explicitly deferred
- Log compaction / snapshot policy (`InstallSnapshot` plumbed through, no
  compaction policy in P1)
- MVCC, sharding, multi-raft (mentioned as long-term goal)
- Exactly-once client sessions

## New Salt-side code

```
salt/cluster/
    consensus/
        raft/        # poached rift core (or raft.py instead of raft/)
        rpc.py       # RPC envelope on cluster_pool_port; kind dispatch
        peer.py      # SaltPeer: non-blocking request_vote /
                     #   append_entries / install_snapshot via per-peer
                     #   pushers; reply via correlation_id over puller
        storage.py   # SaltStorage(BaseStorage) → cachedir/cluster/consensus/
        scheduler.py # TornadoScheduler wrapping ioloop.call_later
        membership.py    # MembershipStateMachine (first FSM)
        service.py   # startup glue invoked from salt-master parent
```

## Decisions made

1. **Initial Raft group bootstrap.** "First node up is leader" — single-server
   bootstrap. First node with empty storage writes initial CONFIG entry
   listing only itself as voter, trivially wins election. Subsequent empty
   nodes start as learners and join via membership change. Nodes with
   non-empty storage resume rather than bootstrap. *Hazard:* two empty
   nodes booting simultaneously create two singletons. Need explicit
   bootstrap signal — leaning toward Option A: `cluster_bootstrap: true`
   config flag honoured only when storage is empty. (Pending final
   confirmation.)
2. **Process owner.** Main `salt-master` parent runs the Node. The parent
   is light enough today. Workers read committed FSM state via
   `__context__` or a local-socket query. Revisit if ioloop contention
   appears.
3. **Transport.** Reuse the existing `cluster_pool_port`. Do not add a new
   port. Multiplex Raft RPCs by adding new event-tag kinds
   (`cluster/raft/request-vote`, `cluster/raft/request-vote-reply`,
   `cluster/raft/append-entries`, `cluster/raft/append-entries-reply`,
   `cluster/raft/install-snapshot`, `cluster/raft/install-snapshot-reply`)
   dispatched in `handle_pool_publish`. Replies use per-peer pushers, same
   pattern as autojoin's `join` → `join-reply`. App-layer correlation via
   `(term, rpc_id)`.
4. **Tick/IO model.** Tornado-based scheduler (matches master ioloop), not
   rift's threaded scheduler.
5. **Non-voting masters.** Implemented as Raft learners
   (`Peer.voting=False`).
6. **Branch strategy.** Develop `consensus` independently of
   `auto_scale_clean_v2`; reconcile after auto_scale stabilises and
   merges.
7. **Asyncio vs callback core.** Prefer **asyncio** for Salt-owned consensus
   glue (transport, waiting on replies, orchestration around the master
   process) as much as practical. Keep **`salt.cluster.consensus.raft`**
   **synchronous** with the existing **callback** surface (`Peer` /
   `ManualPeer`, `register_schedule_timeout`, RPC reply callbacks) so the
   Raft state machine stays easy to unit-test with `ManualTimeoutScheduler`
   and no nested event-loop concerns. Integration layers bridge asyncio I/O
   into those callbacks (e.g. schedule work on the loop, invoke `Node` methods
   and peer callbacks from completed tasks).

## Open questions

1. Confirm Option A (`cluster_bootstrap: true` config flag) for bootstrap
   signal, vs. Option B (`salt-run cluster.bootstrap` CLI), vs. Option C
   (trust ordering — fragile).
2. Where exactly does `service.py` get invoked? `salt/master.py`
   `Master.__init__` after the pool TCP is up, or `salt/channel/server.py`
   alongside the pool. Punted.
3. Whether to produce a file-by-file poach audit (which rift lines move /
   adapt / delete) as an explicit P0 deliverable before any code lands.

## Phased plan

### P0 — scaffolding, no replication
- Poach rift core into `salt/cluster/consensus/raft/` (or `raft.py`) with
  Apache 2.0 headers noting origin
- Wire serialization to `salt.payload` (msgpack)
- Multiplex Raft RPC kinds onto `cluster_pool_port` via
  `handle_pool_publish` dispatcher
- `SaltStorage` under `cachedir/cluster/consensus/` (JSON first; LMDB later if
  throughput demands)
- New config: `cluster_raft_enabled`, `cluster_raft_voting` (voter vs.
  learner), `cluster_bootstrap` (pending bootstrap-flag decision)
- Port poached unit tests using `ManualPeer` / `ManualTimeoutScheduler`

### P1 — leader election only
- Bring up `Node` on each master with statically-configured `cluster_peers`
  as initial peer set; learners per `cluster_raft_voting=False`
- No replicated FSM yet — just observe single-leader emergence and survive
  process kill
- Functional test under `tests/pytests/integration/cluster/` verifying
  single-leader convergence

### P2 — membership FSM (first replicated state)
- `MembershipStateMachine`: `{ voters, learners, version }`
- Commands: `AddVoter`, `AddLearner`, `Promote`, `Demote`, `Remove`
- After auto_scale merges, autojoin handler proposes `AddLearner` via the
  Raft leader rather than broadcasting directly to peers

### P3 — retire dropfile leader election
- AES key rotation driven by Raft leader; replaces
  `salt/master.py:401-419`
- Raft log carries rotation metadata (version, timestamp); key material
  continues to flow over the existing encrypted peer event channel

### P4 — peel off remaining shared-FS dependencies
- Minion key acceptance state → FSM
- Continue peeling subsystems one at a time; keep shared-FS path working
  until each subsystem is fully converted
