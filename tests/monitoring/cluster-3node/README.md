# cluster-3node testbed

3-master Salt cluster + haproxy LB + 1 scale minion (200K dummy
resources) for Phase-3 memory-ceiling + ring-mode verification.

## Topology

- `c3-salt-master-1 / 2 / 3`: 3-master Raft cluster in
  `cluster_id=scale_test`, `cluster_isolated_filesystem=True`.
- `c3-salt-haproxy`: TCP LB in front of the 3 masters.
- `c3-ring-setup`: one-shot sequencing shim.  Creates the
  `resource_index` ring + route + ring_set, waits for `active`,
  exits 0.  Runs BEFORE the minion so the minion's first
  auto-register goes through the ring, not the broadcast fallback.
- `c3-salt-minion-1`: configured with
  `resource_types: [dummy]` + `dummy_resource_count: 200000`.

## Usage

```bash
cd tests/monitoring/cluster-3node

# From a worktree, point SALT_SRC at the worktree root so the
# container bind-mounts the branch's salt/ package.
export SALT_SRC=/home/you/src/salt   # or /home/you/src/salt/.claude/worktrees/<name>
docker compose up -d

# `up -d` returns only after c3-ring-setup exits 0 and the minion is up.
# First-register measurement:
docker exec c3-salt-minion-1 salt-call saltutil.refresh_resources wait=True timeout=600
```

## Why the ring-setup shim

Pre-shim, the minion's auto-register fired as soon as haproxy was up,
before any operator could manually create the `resource_index` ring.
That caused chunks 0..2 (30K SRNs out of 200K) to land via the
replicate fallback (full set to all 3 masters), polluting every master
with "shared" SRNs that the later ring-dispatched chunks could not
prune (the scope-terminal prune only removes SRNs NOT seen this window,
and the replicate-dupes had been seen on every master this window).

The shim runs ring_create / route_set / ring_set before the minion
even starts, making `sum=200000 exact` the stable ring-mode invariant
for a fresh `up -d`.

If you need to measure replicate mode, bring the stack up without the
ring (set `RING_NAME=` to disable the shim's create pass, or just
remove the ring state from the cluster_pki volume after `up -d`).
