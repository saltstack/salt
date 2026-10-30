# Master Topology Overview

Master topology links two or more independent Salt masters so that a
publish on one can reach minions attached to another. You have one Salt
master in each datacenter; with topology configured on both, running
`salt '*' test.ping` on the east master also publishes to the minions
connected to the west master, and their returns come back to the east
CLI. Each master still owns its own minions, keys, job cache, and
config -- topology adds an authenticated master-to-master link on a
separate port (default `4521`) and routes publishes and returns across
it.

## A two-cluster peered topology

```
        +-----------+        peer link        +-----------+
        |  east     |  <------------------->  |  west     |
        |  master   |        TCP 4521         |  master   |
        +-----+-----+                         +-----+-----+
              |                                     |
              | 4505/4506                           | 4505/4506
              |                                     |
       +------+------+                       +------+------+
       | east-m1     |                       | west-m1     |
       | east-m2     |                       | west-m2     |
       +-------------+                       +-------------+
```

Each master only knows about its own minions. The peer link carries
publishes and returns between the two masters.

## How a publish flows

The east operator runs `salt '*' test.ping`. East publishes to its
local minions as usual, and in parallel forwards the publish to every
accepted peer master. West receives the forwarded publish, writes a
breadcrumb mapping the job id back to the inbound link, and publishes
to its own local minions. Returns from west's minions arrive at west's
MWorkers, which look up the breadcrumb and ship the returns back to
east. East's returner stores them alongside the local returns, and the
`salt` CLI prints them.

1. East runs `salt '*' test.ping`.
2. East publishes locally and sends the publish to west over the
   topology link.
3. West writes a breadcrumb (`jid` -> inbound link = east) and
   publishes to its local minions.
4. West's minions return to west's MWorkers.
5. The MWorker reads the breadcrumb and forwards the return to east
   over the same link.
6. East stores the returns and the CLI prints them.

Transit hops (three or more clusters chained) follow the same pattern:
each hop writes a breadcrumb at publish time and uses it to send the
return back out the inbound link.

## Configuration

Topology lives in two files per master: the normal master config, and
a separate `topology.conf` that names this master and lists its direct
peers. A working six-cluster example runs under
`agents/scratch/topology-sandbox/`.

Master config additions on east (`/etc/salt/master`):

```yaml
interface: 0.0.0.0

topology_enabled: True
topology_config_file: /etc/salt/topology.conf
topology_link_port: 4521
```

East's `topology.conf`:

```yaml
cluster_id: east
peers:
  - host: west
    port: 4521
```

West is symmetric: `cluster_id: west`, and a `peers:` entry pointing
at east. Each side also has to accept the other's master-identity
public key with `salt-key -a <peer> --master` -- the same accept
workflow Salt already uses for minions, but on a separate key
directory (`<pki_dir>/masters_pre/`, `<pki_dir>/masters/`).

The sandbox at `agents/scratch/topology-sandbox/` pre-copies keys
between containers in `up.sh` so you can skip the manual accept and
see a working mesh in a few seconds. Don't copy that shortcut into
production -- the accept step is the trust boundary.

## Relationship to syndic

Master topology replaces syndic. Syndic federates jobs through a
top-level master that owns the chain and funnels leaf minions into a
single flat population; it has shipped with Salt for years but has
long-standing operational pain points (opaque failure modes, no
per-peer accept, single point of fan-in). Topology is the successor:
every master stays a first-class master with its own minion set,
links between masters are authenticated per-peer, and publishes and
returns are routed with explicit breadcrumbs rather than funneled.

Syndic (`syndic_master` in master config) is **deprecated**. During
the deprecation window a master may run both `syndic_master` and
`topology_enabled` set so operators can migrate incrementally, but
new deployments should use topology and existing syndic deployments
should plan a cutover. All of syndic's job-federation use cases map
onto topology peering: either a flat mesh of peers, or a tree
expressed as `C@<cluster_id>` targeting across hops.

## Relationship to the 3008.x master cluster

Topology is not a master cluster. A master cluster is several
co-located masters sharing one minion population behind a load
balancer, coordinated via Raft, for HA at a single site. Topology
links separate masters (or separate clusters) across sites. A single
topology node can itself be a Raft master cluster -- the topology
layer treats it as one node with a `cluster_id`. The two features
compose: run a master cluster at each site for local HA, and link
the sites with topology.

## When to use it

Cross-site job delegation. You have a master in each datacenter and
want operators at one site to run jobs that reach minions at the
other, without re-pointing minions or standing up a central syndic.

Administrative boundaries that still need targeted jobs. Two teams
run their own masters with their own change windows and key policies,
but occasionally an operator needs to publish across the boundary.
Topology makes the link explicit and authenticated, with per-peer
accept/reject.

Tiered deployments. A top-level master fans work out to regional
masters it does not directly operate. Each region keeps its own
minion keys and job cache; the top master targets by region with
`salt -C 'C@west' ...`.

## When NOT to use it

Use a 3008.x master cluster when you want HA for one logical master
at one site -- multiple masters, shared minions, failover. That's a
different problem than linking separate masters together. (You can
run master cluster + topology together: HA inside a site, topology
between sites.)

Use neither (just scale one master vertically or run multimaster) if
you don't actually have a cross-site or cross-boundary split. Topology
adds a key-exchange step, a second TCP port, and a routing layer; a
single master or a master cluster is simpler if you don't need the
split.

## Troubleshooting

Handshake stuck in `pending`. `salt-run topology.links` shows
`health: pending_accept`. The peer has your master-identity key in
its `masters_pre/` directory but hasn't promoted it. On the peer, run
`salt-key -L --master` to see pending peers and
`salt-key -a <your_cluster_id> --master` to accept. If the key never
reaches the peer at all, check that `topology_link_port` is open
between the two hosts.

Publish doesn't reach peer minions. Confirm both masters show the
link as `connected` in `salt-run topology.links`. If the destination
cluster is more than one hop away, confirm a periodic
`topology/sum` summary has propagated -- a warning like
`route_publish flooding --- no known route` means gossip hasn't
reached the originator yet. Returns that never arrive usually mean
the breadcrumb expired before the return came back; raise
`topology_breadcrumb_grace` or `topology_breadcrumb_max_age` if your
jobs run long.

---

For the full configuration schema, runner commands, targeting syntax
(`C@<cluster_id>`), key management, and internals, see
`doc/topics/master-topology/index.md`.
