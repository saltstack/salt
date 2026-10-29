# Master Topology

> Status: experimental. Introduced on `master` branch. Wire format,
> config keys, and runner output may change until the feature ships.

## Overview

**Master topology** links multiple independent Salt masters into a
directed graph. Each master runs normally — its own minions, its own
job cache, its own CLI — and gains the ability to forward publishes
and returns across authenticated links to peer masters.

Each link is a dedicated REQ/REP channel on a separate port
(`topology_link_port`, default `4521`), authenticated by a per-master
`master_identity` keypair that is distinct from the master's
minion-facing PKI. Publishes and returns are serialized onto the link,
loop-detected by an authenticated-path field in the envelope, and
replied through a per-jid breadcrumb trail back to the originating
master.

### What topology is not

Master topology is **not** a replacement for a master cluster. On
3008.x, a *master cluster* is a set of co-located masters sharing one
minion population behind a load balancer, coordinated via Raft (see
:ref:`highavailability`). Topology sits one level up: it links
clusters (or solo masters) across sites, boundaries, and
administrative domains. A single topology node may itself be a solo
master or a Raft-coordinated master cluster — the topology layer does
not care, as long as the node has a stable `cluster_id`.

Use topology when you need:

- Cross-site job delegation without re-pointing minions at a
  different master.
- A policy boundary between masters (different operators, different
  change windows) that still allows targeted jobs to cross.
- A tiered deployment where a top-level master can fan work out to
  per-region masters it does not directly manage.

Do **not** use topology to replace syndic in a scale-up / HA
single-site deployment. For that, use master-cluster.

## Vocabulary

The topology code and these docs use three role names for a
master-to-master relationship. **Only one of them is implemented
today.**

**Peer** *(implemented)* — symmetric, bidirectional. Both masters
list each other in their `topology.conf`. Publishes flow both ways;
returns flow back along the breadcrumb trail of the originator.
Every entry in a `peers:` list is a Peer; this is the only link
type the current code supports.

**Controller** *(roadmap)* — a master that can publish *into*
another master's cluster but will not accept publishes *from* it.
A one-way delegation edge.

**Managed** *(roadmap)* — the far end of a Controller edge.
Accepts publishes, sends returns back, no publish authority upward.

**Today every link is a Peer.** The Controller / Managed split is
the planned extension for asymmetric trust and will land as a
per-peer flag in `topology.conf` (something like `role: controller`
/ `role: managed`). Until then, if you need one-way behavior,
enforce it with external access control. Do not try to approximate
it by only listing one side — handshake is mutual and will stay in
`pending_accept` if either side has not accepted the other's
identity.

## Configuration

Topology configuration lives in two places on each master:

1. The master config (`/etc/salt/master`) — a handful of
   `topology_*` opts that gate the feature and tune its runtime.
2. A separate topology config file (default
   `/etc/salt/topology.conf`) — the `cluster_id` and the list of
   peer seed endpoints.

### Master config opts

All opts are optional with defaults. The feature is off until you
flip `topology_enabled`.

| Opt | Default | Meaning |
| --- | --- | --- |
| `topology_enabled` | `False` | Master-switch. Nothing in `salt.topology` imports until this is `True`. |
| `topology_config_file` | `/etc/salt/topology.conf` | Path to the per-master topology config. |
| `topology_link_port` | `4521` | TCP port where this master binds the inbound topology REP socket. |
| `topology_summary_interval` | `30` | Seconds between `topology/sum` gossip emissions to each peer link. |
| `topology_breadcrumb_grace` | `30` | Seconds added to a publish's timeout when computing a breadcrumb's `expiry_at`. |
| `topology_breadcrumb_max_age` | `600` | Absolute ceiling on breadcrumb age regardless of publish timeout. |
| `topology_push_cluster_grain` | `True` | On auth, hand minions a `master_cluster_id` grain naming this master's topology cluster. |
| `topology_detach_quiesce` | `60` | Seconds a detaching peer link stays in `quiescing` state to drain in-flight returns. |
| `topology_summary_grains` | `[]` | Extra grain keys fanned out on the periodic summary. Empty = don't send any. |
| `topology_breadcrumb_cache_size` | `1_000_000` | Breadcrumb MmapCache capacity (entries). |
| `topology_breadcrumb_cache_key_size` | `64` | Key-slot byte width in the breadcrumb MmapCache. |
| `topology_registry_cache_size` | `10_000` | Peer-registry MmapCache capacity (entries). |
| `topology_registry_cache_key_size` | `64` | Key-slot byte width in the registry MmapCache. |
| `auto_accept_masters` | *(absent)* | Mirrors `auto_accept` but for peer-master identity keys. **Not yet honored by the inbound dispatcher** — accept peers manually. |

Two additional handshake knobs are read with `.get()` defaults in
`salt/topology/link.py` but **are not declared in the master config
schema**: `topology_handshake_max_tries` (default `6`) and
`topology_handshake_backoff` (default `2.0` seconds). You can set
them in `/etc/salt/master` and they will be picked up, but they are
not in the public opts table. Treat them as internal tunables.

A minimal topology-enabled master config:

```yaml
# /etc/salt/master
interface: 0.0.0.0

topology_enabled: True
topology_config_file: /etc/salt/topology.conf
topology_link_port: 4521
```

### `topology.conf`

The per-master topology file is a small YAML mapping. The canonical
form in the sandbox is `agents/scratch/topology-sandbox/conf/topology-east.conf`:

```yaml
# This master's identity in the topology graph.  Short, lowercase,
# unique within the graph.  Must match [a-z0-9][a-z0-9_-]*.
cluster_id: east

# Seed endpoints for direct peers.  Each master declares only its
# direct peers; descendants and transit paths are learned via
# gossip at runtime.
peers:
  - host: west
    port: 4515
  - host: east-sub
    port: 4515

# Optional: tag-glob subscription list this master wants from each
# peer.  Default is job events only ("salt/job/*/ret/*" and
# "salt/job/*/new") -- cheapest wire volume, lowest surprise.
# event_subscriptions:
#   - "salt/job/*/ret/*"
#   - "salt/job/*/new"
```

Validation (`salt/config/topology.py:validate_topology_config`):

- `cluster_id` is required and must match `[a-z0-9][a-z0-9_-]*`.
  Reserved names (`__identity_pub__`, `__cluster_meta__`,
  `__peer_index__`) are rejected.
- `peers` is a list of `{host, port, finger}` mappings. `port`
  defaults to this master's own `topology_link_port` when omitted.
  `finger` is an optional pinned fingerprint; if set and the
  presented key does not match, handshake aborts with a CRITICAL
  log line.
- `event_subscriptions` must be a list of valid glob patterns.
- Disabling topology (removing the file or setting
  `topology_enabled: False`) is safe: `load_topology_config` returns
  an inert config and no runtime code loads.

A full example — a six-cluster mesh — lives at
`agents/scratch/topology-sandbox/conf/topology-*.conf`.

## Peer acceptance

A peer relationship is bootstrapped by exchanging each master's
`master_identity` **public** key, the same way `salt-key` does for
minions.

### Keys

On first start of a topology-enabled master, the publish daemon
generates (if absent) a keypair at:

```
<pki_dir>/master/master_identity.pem      # private, 0400
<pki_dir>/master/master_identity.pub      # public
```

This is distinct from the minion-facing `master.pem` / `master.pub`
pair. The private half never leaves the master.

### Trust directories

Peer identity keys land in sibling directories of `<pki_dir>`:

| Directory | Meaning |
| --- | --- |
| `<pki_dir>/masters_pre/<cluster_id>.pub` | Seen in a handshake but not yet accepted. The peer stays in `PENDING_ACCEPT`. |
| `<pki_dir>/masters/<cluster_id>.pub` | Accepted. Handshake can complete. |
| `<pki_dir>/masters_rejected/<cluster_id>.pub` | Explicitly rejected. Handshake responds `rejected`. |

This mirrors the minion `minions_pre` / `minions` / `minions_rejected`
layout one-to-one.

### Accepting a peer in production

Use `salt-key --master`:

```
# list master-identity keys on this master
salt-key -L --master

# accept a specific peer
salt-key -a west --master

# or accept all pending peers
salt-key -A --master
```

The topology runner wraps the same semantics for automation:

```
salt-run topology.trust west accept
salt-run topology.trust west reject
salt-run topology.trust west fingerprint
salt-run topology.trust west delete
```

### Shortcut in the sandbox

The sandbox at `agents/scratch/topology-sandbox/` short-circuits the
accept step: `up.sh` generates each master's keypair and pre-copies
each public key into every peer's `pki/<local>/masters/<peer>.pub`
directory. This is the on-disk equivalent of
`salt-key -a <peer> --master` run on every master before first boot.
Do **not** copy this pattern into production — it bypasses the
operator trust decision that acceptance is supposed to encode.

## Targeting across clusters

Topology extends Salt's compound matcher with a new scope token.

### `C@<cluster_id>` — direct cluster scope

The `C@` prefix names one or more topology `cluster_id`s as the
publish's destination:

```
# single cluster
salt -C 'C@west' test.ping

# comma-separated list
salt -C 'C@west,east-sub' test.ping

# combined with other matchers
salt -C 'C@west and G@os:ubuntu' test.ping
```

Scope extraction (`salt/topology/router.py:extract_cluster_scope`)
pulls every top-level `C@` token out of the compound expression,
determines which clusters are destinations, and strips the `C@`
clauses from the target before it reaches the local
`CkMinions` compound matcher — so each cluster evaluates the
remainder of the expression against its own minion population.

Edge cases:

- A `C@` token adjacent to `or` at the same paren depth
  (`C@east or web-*`) means "flood": the OR cannot be resolved to a
  single cluster, so every peer receives the publish.
- `not C@east and web-*` is **not stripped** — the `not` has to
  reach `CkMinions` so cluster-local evaluation sees the negation.
- Absence of any `C@` token means "flood per policy." Every peer
  gets a copy and evaluates its own minions.

### `N@<nodegroup>` with embedded `C@`

Nodegroups whose definition contains `C@` tokens are expanded
*before* scope extraction, so a `salt -N production ...` with a
nodegroup defined as `C@west and web-*` is correctly scoped to
`west` only.

### Route learning (gossip)

Each master periodically sends a `topology/sum` summary to every
peer link containing its own `cluster_id`, minion counts, and the
authenticated `path` the summary traversed. Receiving peers record
`(destination_cluster_id → (next_hop_peer_id, hop_count))` in an
in-process routing table. When `route_publish` is asked to send to a
non-adjacent cluster, it consults this table to pick the correct
transit peer.

**Flood-on-unresolved**: if any destination has no known route,
`route_publish` logs a warning and falls back to flooding every peer
link. This is deliberate — "better a duplicate than silently dropped"
— and matches the policy at transit hops (`forward_publish` uses the
same rule). The warning looks like:

```
topology: route_publish flooding --- no known route for
destination(s) ['east-sub'] (known routes: [])
```

If you see this persistently, the summary gossip from the far
cluster has not reached the originator — check that every link along
the path is in `connected` state via `salt-run topology.links`.

## Return path

Returns are not routed by matching — they're routed by *breadcrumbs*
written at publish time on every transit hop. Each hop knows which
inbound link a jid arrived from, and sends the return back out the
same link.

### Breadcrumb lifecycle

When `forward_publish` accepts a publish, it writes an entry to the
breadcrumbs MmapCache at
`<pki_dir>/master/topology_breadcrumbs.mmap*`. Key is
`<cluster_id>:<jid>`; value is `{"link_cluster_id": <inbound peer>,
"expiry_at": <ts>}` where `expiry_at` is
`now + min(publish.timeout + topology_breadcrumb_grace,
topology_breadcrumb_max_age)`. Expired entries are swept by a
periodic `cleanup`; readers also treat expired as absent. The cache
file persists across publish-daemon restarts, so in-flight returns
remain routable through a master restart.

### Return hand-off

Minion returns arrive at any MWorker (not necessarily the publish
daemon). The MWorker is a **reader** of the breadcrumbs cache; on
hit, it fires a single event:

```
salt/topology/return/<origin_cluster_id>/<jid>
```

The publish daemon runs a dedicated subscriber
(`_start_return_subscriber` in `salt/topology/link_manager.py`) that
picks up the event, looks up the inbound link cluster from the
breadcrumb, and calls `PeerMasterLink.send_return` on that link —
one return, one hop, back toward the origin. The next master
upstream does the same lookup against its own breadcrumbs until the
return reaches the originating cluster, where the local returner
stores the result.

### Origin detection

`_jid_is_local_origin` consults breadcrumbs on the current master
to decide whether an inbound return should be forwarded upstream or
is already home. A missing breadcrumb for a return the master
expected to see is almost always a cleanup race (publish timed out
and swept the breadcrumb before the return arrived); the return is
dropped with a `debug` log line and the originating `salt` CLI will
simply time out waiting.

### Transit forwarding

In `_dispatch_pub`, the inbound dispatcher calls
`forward_publish`, gets back the list of next-hop links, and
fire-and-forgets a `send_publish` on each. This is intentionally
asynchronous — the inbound REP socket acks the sender as soon as the
breadcrumb and loop checks pass, so a slow downstream peer cannot
back-pressure the whole chain. Return hand-off above is the
counterpart on the return path.

## Operations

The `topology` runner (`salt/runners/topology.py`) is the operator
surface. It loads only when `topology_enabled: True`. All read
commands fall back to on-disk state (PKI dirs, breadcrumb mmaps,
registry mmap) so they work from a short-lived `salt-run` process
that does not share state with the publish daemon.

**`topology.status`** — tree view: this cluster's `cluster_id`,
minion count, and one row per known peer with state and
`last_summary_at`.

**`topology.peers`** — every peer in every state across
`masters/`, `masters_pre/`, `masters_rejected/`, and
`topology.conf`. States: `configured`, `pending`, `attached`,
`rejected`.

**`topology.links`** — live link health per peer: `health`
(`connected`, `connecting`, `degraded`, `disconnected`,
`pending_accept`, `quiescing`), endpoint list, `last_summary_at`,
and the global `breadcrumbs_active` count. Peers whose key is in
`masters/` but whose handshake has never completed show as
`disconnected` — the usual sign that the far side has not accepted
this master's identity.

**`topology.graph`** — graph known to this master. `fmt="text"`
(default), `fmt="dot"` (Graphviz), or `fmt="json"`.

**`topology.find <minion_id>`** — asks every known cluster whether
it has an accepted key for `<minion_id>`. The remote fan-out needs
live outbound links; from a `salt-run` subprocess (the usual case),
this degrades to a local-only lookup.

## Example topology

The sandbox at `agents/scratch/topology-sandbox/` runs a six-cluster
three-level mesh in Docker. Each cluster has one solo master and
one or two minions:

```
                       east ──peer── west
                        │             │
                       peer          peer
                        │             │
                     east-sub      west-sub
                        │             │
                       peer          peer
                        │             │
                 east-sub-sub   west-sub-sub
```

Each master's `topology.conf` lists only its *direct* peers.
`east-sub` and `west-sub` are not peered with each other, so a
publish from `west` to `C@east-sub` must transit through `east`.
The routing table built from gossip picks `east` as the next hop
once a summary from `east-sub` has reached `west` via `east`.

`./up.sh` builds the images, generates each master's
`master_identity` keypair, pre-copies the public halves into the
`masters/` directories of every direct peer, and starts the
containers. `./smoke.sh` runs a battery of local and cross-cluster
`test.ping` publishes. The sandbox is the fastest way to see a
multi-cluster publish go end-to-end:

```
docker exec topo-east salt '*' test.ping                     # local
docker exec topo-east salt -C 'C@west' test.ping             # peer
docker exec topo-east salt -C 'C@east-sub-sub' test.ping     # transit
```

See `agents/scratch/topology-sandbox/README.md` for the current set
of known gaps surfaced by the four- and six-cluster shapes.

## Troubleshooting

### Link stuck in `pending_accept`

Shows up in `salt-run topology.links` as `health: pending_accept`
and in logs as periodic retry lines. The far side has not accepted
this master's identity key — its `masters_pre/<this_cluster_id>.pub`
is populated but it has not been promoted to `masters/`.

- On the peer, run `salt-key -L --master` to see pending peers.
- `salt-key -a <this_cluster_id> --master` to accept.
- Verify fingerprint parity on both sides with
  `salt-run topology.trust <peer> fingerprint`.

If the key never shows up on the peer's side at all, the inbound
listener is likely not bound — check that `topology_link_port` is
free (`ss -ltn | grep 4521`) and that the peer's firewall allows
the port.

### `flooding --- no known route for destination(s)`

Logged at WARNING in `route_publish` and at DEBUG in
`forward_publish`. Means the destination `cluster_id` is not a
direct peer and no `topology/sum` summary has yet taught the local
routing table about it. The publish still goes out — flooded to
every peer — but the warning says gossip is lagging.

Expected briefly after startup (summary interval defaults to 30s).
If persistent, inspect `salt-run topology.links` for a link that
is `degraded` or `disconnected` on the path to the destination.

### Breadcrumb miss on return

A return arrives at an MWorker, the MWorker checks the breadcrumbs
cache, finds nothing, and the return is dropped as "not ours." The
usual causes:

- Publish's timeout + `topology_breadcrumb_grace` already elapsed
  before the return arrived. Raise `topology_breadcrumb_grace` or
  `topology_breadcrumb_max_age`.
- Publish daemon restarted *and* the mmap file was wiped. The file
  is designed to survive restarts; only `rm` or a full `pki_dir`
  wipe clears it.
- Transit hop never saw the publish (dropped during a flap). The
  breadcrumb never got written on that hop, so the return falls
  through. Only recourse is re-run the job.

### `tampered path` warning

```
topology: forward_publish rejecting tampered path
(path tail=..., inbound peer=...)
```

Means an inbound publish's self-reported `path[-1]` did not match
the authenticated link identity. This is a security check — a hop
cannot claim to have come from a cluster it is not authenticated
as. Legitimate causes: a misconfigured bridge that proxies topology
traffic without re-authenticating. Illegitimate causes: an attacker
on the wire. The publish is dropped either way.

### Minions missing from a cross-cluster publish

Expect the full `--timeout` wait on the originating CLI for
cross-cluster publishes: the origin master cannot know the peer
cluster's minion list at publish time, so there is no fast-path
"all minions returned, exit early" like there is for a local
publish. This is a known limitation and will not change without a
protocol-level minion-set exchange.

## See also

- `rfcs/master-topology.md` — design rationale and security model.
- `salt/topology/` — runtime implementation.
- `salt/config/topology.py` — config schema and validator.
- `salt/runners/topology.py` — operator commands.
- `agents/scratch/topology-sandbox/` — runnable six-cluster example.
