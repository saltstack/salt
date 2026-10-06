# Multi-Ring / Multi-Raft Cluster Design

Working notes for the evolution from "single global ring, single Raft
group, every master votes" to "named rings per cache type, per-ring
Raft groups, capped voter and ring-member counts".

The original sketch (preserved below as historical context) is now
mostly **landed**.  This top section describes the shipping shape;
read it first if you want operational context, and consult the
"Original design sketch" section if you're tracing decisions.

## Shipping shape (2026-05-16)

Multi-ring landed across seven slices.  All 722 tests in the cluster
suites pass.  Operator surface and on-the-wire shape are stable from
here.

### Architecture

```
            cluster Raft log (single group, "cluster" id)
            ┌──────────────────────────────────────────┐
            │ MembershipStateMachine        (CONFIG)   │
            │ RingRegistryStateMachine      (RING_REGISTRY) │
            │ RoutingStateMachine           (ROUTE)    │
            │ RingConfigStateMachine        (RING_CONFIG, legacy) │
            └──────────────────────────────────────────┘
                                │
              spawns per-founder
                                v
       ring_X Raft log (own group, own log/term/leader)
       ┌─────────────────────────────────────┐
       │ MembershipStateMachine  (per-ring CONFIG) │
       │ RingConfigStateMachine  (per-ring policy) │
       └─────────────────────────────────────┘
```

The cluster log is the only consensus state every master needs to
agree on; per-ring logs handle their own membership and policy
churn so a ring outage doesn't take down other rings or the cluster.

### Substrate

* `SaltStorage(node_id, opts, ring_id="cluster")` — on-disk path
  scheme: `cachedir/cluster/consensus/<node_id>/<ring_id>/`.
* RPC envelope carries `raft_group_id` (default `"cluster"`).
  `salt/cluster/consensus/rpc.py:pack/unpack` handle it; pre-multi-ring
  envelopes default to the cluster group on decode.
* `salt/cluster/consensus/peer.py:RaftDispatcher` accepts either a
  single `Node` (treated as cluster) or `dict[str, Node]`; routes
  inbound RPCs by `raft_group_id`.  `register_node`/`unregister_node`
  let `RaftService` mutate the routing table at runtime.
* `salt/cluster/consensus/service.py:RaftService` keeps `self._node`
  for backward compat and `self._nodes = {"cluster": self._node}` as
  the multi-ring registry.  `_heartbeat_tick` iterates all groups.

### Cluster-log state machines

* `RingRegistryStateMachine` (`raft/log.py`) — registry of named
  rings.  Each entry: `{ring_id, founding_voters, status}`.  Snapshot
  round-trips; `on_change` fires per commit.
* `RoutingStateMachine` (`raft/log.py`) — data-type → ring mapping
  (or `None` for broadcast).  Snapshot round-trips; `on_change`
  populates the per-process routing snapshot.
* New `LogEntryType.RING_REGISTRY = 4` and `LogEntryType.ROUTE = 5`;
  the legacy `RING_CONFIG = 3` continues to drive the single-ring
  fallback that pre-multi-ring callers use.

### Per-ring lifecycle

`RaftService._on_ring_registry_change` brings up a per-ring `Node`
(with its own `SaltStorage(ring_id=...)`, `MembershipStateMachine`,
and `RingConfigStateMachine`) whenever a registry entry commits and
this master is in the founder list.  `status="destroyed"` tears down
the local `Node` and drops it from the dispatcher; on-disk state is
preserved so re-create with the same id recovers state.

### Ring registry / routing surface

`salt/cluster/ring_membership.py` is now a registry of named rings.

* `get_ring(name)` lazily creates an empty `HashRing` per name.
* `rebuild(name, voters, replicas=1)` keyed by name; legacy
  `rebuild(voters)` keeps targeting the `"cluster"` ring.
* `owns_for(opts, data_type, key)` consults `_ROUTING` first: no
  route ⇒ broadcast (True); routed to an unknown/empty ring ⇒ False;
  routed to a populated ring ⇒ defers to `ring.owns()`.
* `set_route(data_type, ring_id)` / `drop_ring(name)` are called by
  `RaftService` on commits to keep the per-process snapshot in sync.

### Gate sites

`salt/master.py:1171,1187` (job submission + job return mirroring)
call `ring_membership.owns_for(self.opts, "jobs", jid)`.  No routing
entry for `"jobs"` keeps today's broadcast behaviour; an operator
flips it to a ring with `cluster.route_set`.

### Operator runners

All in `salt/runners/cluster.py`:

| Runner | Purpose |
|---|---|
| `cluster.ring_create name=X voters=[…]` | Propose `RING_REGISTRY` entry creating ring X |
| `cluster.ring_destroy name=X` | Propose destroy (status="destroyed") |
| `cluster.route_set data_type=… ring=…` | Propose `ROUTE` entry binding data_type to ring |
| `cluster.route_clear data_type=…` | Propose route → `None` (back to broadcast) |
| `cluster.ring_set name=X members=voters replicas=N` | Propose `RING_CONFIG` on ring X's *own* log (per-ring policy) |
| `cluster.shed_unowned ring=X banks=[…] dry_run=…` | Local: drop cache entries this master no longer owns |
| `cluster.collect_from_peers channels=[…]` | Pull keys/denied_keys from every peer via the existing state-sync chunk transport |
| `cluster.members` | Read-only membership + leader + health |
| `cluster.ring_info` | Read-only ring snapshot |
| `cluster.sync_roots` | Pre-existing: push file_roots/pillar_roots to peers |

Each runner that proposes a Raft entry fires a `cluster/runner/*`
local event; `salt/channel/server.py:publish_payload` intercepts and
dispatches to the `RaftService` propose helpers in the publish
daemon.  Same pattern as `cluster.sync_roots`.

### Reversible migration flow

Going in (broadcast → ring=jobs):

1. `salt-run cluster.ring_create name=jobs voters='[m1,m2,m3]'`
2. (Registry commits; founders spin up the ring.)
3. `salt-run cluster.route_set data_type=jobs ring=jobs`
4. (Routing commits; gates start filtering writes.)
5. `salt-run cluster.shed_unowned ring=jobs dry_run=True` (preview)
6. `salt-run cluster.shed_unowned ring=jobs` (commit drops)

Going out (ring=jobs → broadcast):

1. `salt-run cluster.collect_from_peers` (each master gathers full set)
2. (Operator confirms every master succeeded.)
3. `salt-run cluster.route_clear data_type=jobs`
4. (Routing commits; gates broadcast again.)
5. (Optional) `salt-run cluster.ring_destroy name=jobs`

The asymmetry — drop **after** policy flip going in, collect
**before** policy flip going out — is what keeps the window safe.

### Recommended production opts

A fresh cluster that wants the multi-ring job-cache sharding from
day one sets:

```yaml
# salt/master.d/cluster.conf — same on every master

cluster_id: my-cluster
cluster_peers:
  - 10.0.0.1
  - 10.0.0.2
  - 10.0.0.3
interface: 10.0.0.1       # this master's address; differs per master

# Job cache through salt.cache.Cache so the ring gate can shard it.
master_job_cache: salt_cache
cache: mmap_cache         # or localfs if mmap_cache is unavailable

# Optional but recommended: cap the cluster's voter pool and let the
# watchdog auto-replace failed voters.  Defaults are
# unlimited/disabled to preserve pre-multi-ring behaviour.
cluster_max_voters: 5
cluster_min_voters: 3
cluster_auto_replace_voters: true
cluster_voter_timeout: 10.0
```

After the master daemon is running with these opts, create a ring
and route the jobs data type to it from any master:

```bash
salt-run cluster.ring_create name=jobs \
    voters='["10.0.0.1","10.0.0.2","10.0.0.3"]'
salt-run cluster.route_set data_type=jobs ring=jobs
```

Operators upgrading an existing ``master_job_cache: local_cache``
cluster should:

```bash
# 1. Drain incoming jobs (operator-specific).
# 2. Stop every master.
# 3. On each master, migrate the on-disk job cache into the salt_cache
#    bank layout.  --dry-run first to preview the count.
salt-run cluster.migrate_jobs_to_cache dry_run=True
salt-run cluster.migrate_jobs_to_cache

# 4. Flip master_job_cache + cache opts as shown above.
# 5. Restart every master.
# 6. Verify with cluster.rings / cluster.routes / cluster.members.
```

### Known limitations / follow-ups

* **`cluster.collect_from_peers` v1 covers the four state-sync
  channels and any ``bank:<bank>`` channel.**  The default targets
  the four ``jobs/*`` banks the salt_cache returner writes through;
  operators routing other caches name them explicitly via the
  ``banks=`` parameter.  PKI keys (``keys`` / ``denied_keys``) stay
  broadcast — see the ``master.py:1195-1208`` comment.
* **Non-member writes are no-ops in v1.**  A master that is not a
  ring member but receives a job event for that ring's data type
  drops the write rather than delegating to a ring member over RPC.
  ``ring_membership.drop_stats`` records ``not_a_member`` counts so
  operators can spot a misconfigured load balancer; the rate-limited
  WARN log line is the loud signal.  Delegate-on-miss is a future
  RPC.
* **Legacy `RingConfigStateMachine` still lives on the cluster log.**
  Functionally inert in multi-ring deployments — per-ring policy is
  on per-ring logs.  Removing the cluster-log registration is a
  cleanup follow-up, not a blocker.

---

## Original design sketch

The rest of this document is the pre-implementation design sketch.
It's preserved for context on the decisions that shaped the shipped
code.  Open questions noted in the sketch have all been resolved:

* Q1 (ring lifecycle): dynamic via `cluster.ring_create` / `ring_destroy`.
* Q2 (default rings): pre-multi-ring callers default to the `"cluster"`
  ring; new code uses named rings via `route_set`.
* Q3 / Q9 (voter selection): operator-specified in the create call.
* Q4 (decommissioning): tear down local Raft group; on-disk state
  preserved for recovery; routes that pointed there are operator's
  responsibility to clear via `route_clear` first.
* Q5 (snapshot scope): each ring's `SaltStorage(ring_id=…)` snapshots
  independently into its own on-disk path.
* Q6 / Q7 / Q8 (voter caps, operator overrides, auto-replacement):
  landed in earlier slices (`cluster_max_voters`,
  `cluster.promote`/`demote`, voter-health watchdog).
* Q10 (persistence of voter-vs-ring-member status): per-ring
  `MembershipStateMachine` persisted via the multi-SM envelope, same
  treatment as the cluster log.

(Working notes for the proposed evolution from "single global ring,
single Raft group, every master votes" to "named rings per cache type,
per-ring Raft groups, capped voter and ring-member counts".)

## Today (baseline)

* **One Raft group per cluster.** Every master in `cluster_peers`
  starts as a voter (`voting=True` is the default in
  `salt/cluster/consensus/raft/node.py:62` and
  `salt/cluster/consensus/service.py:69`).
* **Late joiners become non-voting learners** via
  `RaftService.notify_peer_joined` (`service.py:359`).  The leader
  replicates the log to them; once `match_index >= log.index`
  (`node.py:703-722`) it proposes a CONFIG entry promoting them to
  voter.  No permanent observer/learner role.
* **One global ring.**  `_on_membership_change` calls
  `salt.cluster.ring_membership.rebuild(voters)` at `service.py:218`.
  The ring is a singleton (`salt/cluster/ring_membership.py`), so every
  cache type that wants ring routing shares the same node set.
* **Ring config entries already exist.**
  `LogEntryType.RING_CONFIG = 3` and `RingConfigStateMachine` were
  added in `212c6d97bb2`.  Today they ride the single cluster Raft log;
  the runner `cluster.ring_set` raises `NotImplementedError` because
  the runner→master propose path was deferred (see `GAPS.md`).
* **Heap segment cap.**  `mmap_cache.DEFAULT_MAX_SEGMENT_BYTES = 1
  GiB` (`salt/utils/mmap_cache.py:79`).  Tunable via
  `mmap_cache_max_segment_bytes` / `mmap_key_max_segment_bytes`.  Not
  driven by ring config.

## Decisions locked in

1. **Voter count is bounded** per Raft group.  Default unlimited
   (preserve current behaviour); operator opts in via a cap.
2. **Ring-member count is bounded** per ring.  Independent cap.
3. **Voter set and ring-member set are decoupled.**  A master can be a
   voter without owning ring work, or a ring member without voting.
   They are not subset-related.
4. **First-pass behaviour on member loss may halt.**  Auto-replacement
   of a dead voter / dead ring node by promoting a learner / catching-
   up peer is a follow-up.  Acceptable because log replication reaches
   non-voting peers, so eventual promotion is always possible.
5. **A separate Raft log per ring.**  Multi-Raft architecture — each
   ring is its own Raft group with its own log, term, leader, commit
   index, and voter set.
6. **Multiple rings per cluster, one per cache type.**  Examples: a
   `minion-keys` ring, a `jobs` ring, a `pillars` ring.  Each cache
   backend declares which ring it uses.
7. **Ring-group voters can be any cluster node.**  Not constrained to
   cluster-Raft voters.

## Architecture that falls out

### Cluster Raft (singular) — control plane

Owns everything cluster-wide that isn't per-ring:

* Cluster-wide voter/learner membership (today's
  `MembershipStateMachine`).
* **Ring definitions.**  A registry of
  `{ring_name → {voter_cap, node_cap, cache_types, initial_voters}}`.
  Either a new entry type or a new SM that every node replays so
  every node learns which rings exist.

### Ring Raft groups (N) — data-plane routers

One per logical ring / cache type.  Each one owns:

* Its own `LogStorage` file (independent snapshot / compaction).
* Its own term, leader, commit index, voted-for.
* Its own voter set (subset of cluster nodes, bounded by `voter_cap`).
* Its own ring-member set (the masters that actually own work for
  this cache; bounded by `node_cap`).  Independent of voters.
* A `RingMembershipSM` whose `on_change` hook calls
  `ring_membership[ring_name].rebuild(members)` locally.

### Cache → ring binding

Each cache driver declares its ring name in config:

```yaml
keys.cache_driver_ring: minion-keys
jobs.cache_driver_ring: jobs
pillars.cache_driver_ring: pillars
```

Ownership queries become
`ring_membership.get_ring(name).owns(opts, key)`.  The
`salt/cluster/ring_membership.py` singleton becomes a registry keyed
by ring name.  Cache types that don't opt into a named ring use a
`default` ring for backwards compatibility.

### Bootstrap order

1. Cluster Raft commits a `RING_DEFINITION` entry: "create ring X
   with these caps and initial voters".
2. On apply, every node instantiates a local Raft `Node` for ring X
   bound to a new log file, peers configured from the entry's voter
   list.
3. Multiplexed transport tags each AppendEntries / RequestVote /
   InstallSnapshot with `raft_group_id` (cluster-id or ring-name);
   `SaltPeer` dispatches to the right group.
4. Ring X's leader emits its own membership entries; each apply
   fires `ring_membership["X"].rebuild`.

### Cost shape

N ring groups × per-group heartbeats, timers, log files.  With ~5
cache types and 3-voter rings, well below what etcd / CockroachDB
live with.  Standard mitigations (group ticking, batched AppendEntries
over the shared transport) available later if N grows.

## Implementation surface (where it touches today's code)

* `salt/cluster/consensus/service.py` — `RaftService` becomes a
  manager of multiple `Node` instances rather than owning one.
  `_on_membership_change` for the cluster group still updates
  cluster membership; new per-ring callbacks update each ring's
  membership.
* `salt/cluster/consensus/raft/node.py` — gains a `raft_group_id`
  field on every RPC.  `notify_peer_joined`'s promotion gate at
  `node.py:703-722` reads its group's `voter_cap` before proposing
  promotion.
* `salt/cluster/consensus/peer.py` / transport — dispatches incoming
  RPCs to the addressed group.
* `salt/cluster/ring_membership.py` — becomes a registry of named
  rings; `get_ring(name)` replaces the singleton accessor; `rebuild`
  takes a ring name.
* `salt/cluster/consensus/storage.py` — supports multiple
  `SaltStorage` instances, one per group, each with its own
  persistent path.
* `salt/runners/cluster.py` — `ring_set` becomes a per-ring propose
  call; new `ring_create` / `ring_drop` runners for the cluster Raft.
* `salt/master.py` — gate sites use `ring_membership.get_ring(name)`
  with the cache's declared ring name instead of the global ring.

## Open questions

1. **Ring definition lifecycle.**  Are rings created at cluster init
   via static config, or dynamically via a runner
   (`cluster.ring_create name=jobs voter_cap=3 node_cap=10
   cache_types=[jobs]`)?  Static is simpler.  Dynamic matches how
   `ring_set` is shaped today.

2. **Default rings.**  Ship with a default `default` ring that all
   cache types use unless they opt into a named ring?  Keeps the
   migration path from "today's one ring" to "many rings" trivial.

3. **Voter selection for new ring groups.**  When the cluster commits
   "create ring X", who are X's *initial* voters?  Operator-specified
   in the create call, lowest-N-by-node-id from current cluster
   voters, or random-N?

4. **Decommissioning a ring.**  Drop a `RING_DEFINITION` entry →
   every node tears down that local Raft group, deletes its log
   file.  Cache callers that were routing via it fall back to…
   what?  Single-node ownership?  Reject?  Worth a contract
   decision.

5. **Snapshot scope.**  Each ring group snapshots independently.
   Cluster Raft snapshots independently.  The snapshot envelope
   `raft.snapshot.v1` already does multi-SM serialisation, so this
   works — but the envelope writer per group becomes one-of-its-own-
   SMs, not the global multi-SM bundle.

6. **Voter cap enforcement at static startup.**  Today every address
   in `cluster_peers` becomes a voter.  With a cap, if
   `len(cluster_peers) + 1 > max_voters` we need a deterministic
   voter-subset selection rule (lowest-id-wins, or first N in the
   configured list) and the rest start as learners.

7. **Operator override.**  A runner like `cluster.promote <id>` /
   `cluster.demote <id>` so ops can pick who votes when the
   deterministic rule picks wrong.

8. **Auto-replacement on member loss.**  Today a dead voter stays in
   `voters` until manually removed.  With caps, the leader should
   want to demote a missing voter / ring node and promote a healthy
   learner — otherwise a single death stalls the group forever.  New
   state machine.  Locked as a follow-up, not first-pass.

9. **Voter set of each ring group.**  Decided: "any node in the
   cluster, bounded by per-ring cap".  How are they chosen at ring-
   create time?  Same answer as Q3.

10. **Persistence of voter-vs-ring-member status.**  The membership
    state machine is already snapshot-persisted across log
    compaction (`c53e9bec3dd`).  Each ring group's SM needs the same
    treatment so restart doesn't re-promote everyone.

## Smallest shippable subset

If the above is the long-term shape, a sensible first slice that
preserves today's behaviour by default:

* `cluster_max_voters` opt (default unlimited).  Gate
  `notify_peer_joined` promotion (`raft/node.py:708`) on it.  Don't
  touch static `cluster_peers` startup — operator's responsibility to
  keep that ≤ cap.
* `cluster_max_ring_nodes` opt (default unlimited).
  `_on_membership_change` clamps `voters` → first N (sorted node id)
  when calling `ring_membership.rebuild`.
* No multi-Raft yet; no per-cache-type rings yet.  Single global
  ring continues to ride the cluster Raft via `RING_CONFIG` entries.
* Auto-replacement deferred; halting on member loss is the
  first-pass contract.

Multi-Raft and named rings come in follow-ups, gated on the open
questions above.
