# Design: `topology/pub-ack` + `topology/pub-complete`

**Status**: Phase 1 / 1.5 / 2 / 3 landed; this doc stays as the
authoritative spec for the shape.
**Author**: dwoz
**Scope**: `salt/topology/`, `salt/client/__init__.py`, `salt/master.py`
**Target**: `master` (Potassium)

## Motivation

Master-topology currently floods publishes to peer masters and waits
for returns to arrive. The originating CLI has no deterministic way
to answer two basic questions:

1. **Who should I wait for?** — peers independently match the target
   expression against their rosters; the originator never learns how
   many minions each peer accepted. The CLI falls back to "whatever
   minions returned so far" ∪ "whatever the master's own matcher
   found" — missing minions on remote peers are indistinguishable
   from unreachable ones.
2. **Am I done?** — Salt has no `salt/job/<jid>/complete` event (by
   design — see rationale below). The CLI's existing
   `order_masters` + `syndic_wait` logic infers completion from
   silence, which is a probabilistic bet with a one-size-fits-all
   grace period.

Syndic solved this for its own topology by letting the CLI grow its
expected-minion set as syndics self-reported minion lists, bounded
by a configurable `syndic_wait`. Master-topology has no equivalent;
peers are silent after accepting a flooded publish.

This design adds two authenticated topology frames —
`topology/pub-ack` and `topology/pub-complete` — that give the
originating CLI deterministic answers to both questions, with zero
new master-side job state and no change to Salt's publish-return
protocol semantics.

## Non-goals

- **No `job-complete` event on the master's local bus.** Completion
  stays a client-side concept; the CLI remains the arbiter. This
  preserves the existing invariant that the master is a stateless
  message broker.
- **No change to minion-side protocol.** Minions see a normal publish
  and send a normal return; the new frames are strictly
  master-to-master.
- **No new target-expansion semantics.** Publishes still flood;
  peers still match locally. The ACKs *report* local-match results,
  they don't *decide* them.

## Wire format

Both frames reuse the existing `PeerMasterLink` session (TCP 4521,
AES-signed envelope, breadcrumb-authenticated path). They slot into
the module-level `_DISPATCH_TABLE` at `salt/topology/link_manager.py`
alongside the current `topology/pub` / `topology/ret` / `topology/evt`
/ `topology/sum` tags.

### `topology/pub-ack`

Sent by each peer that accepts a flooded `topology/pub`, immediately
after it has matched the target against its local roster and
*before* dispatching to its own minions. One frame per peer per jid.

```python
{
    "cmd": "topology/pub-ack",
    "tag": "topology/pub-ack",
    "origin_cluster_id": <peer-cluster-id>,       # SENDER cluster
    "session_generation": <int>,                  # session continuity
    "load": {
        "jid":                 <str>,
        "target_cluster_id":   <str>,             # ORIGINATOR cluster
        "matched_minion_ids":  [<str>, ...],      # may be empty
        "topology": {
            "origin": <peer-cluster-id>,
            "path":   [<cluster-ids traversed>],
        },
    },
}
```

**Semantics**:

- `matched_minion_ids` is the exact set the peer *will* publish to
  after this ack. If zero (compound didn't match anything locally)
  the peer sends an empty-list ack rather than silence, so the
  originator can distinguish "didn't match" from "peer unreachable."
- Fired from `_dispatch_pub` on the receiving side, right after
  `router.forward_publish` returns its `(links, local_match)` tuple
  and *before* `_publish_to_local_minions` dispatches. This way an
  ack is guaranteed to precede any return from the acked peer, which
  lets the originator maintain the invariant that `expected_set`
  grows before `returned_set`.
- Transit peers also ack: a peer master forwarded to by its parent
  will send `pub-ack` upstream for its own matched set. The originator
  gets one ack per peer in the flood, not just leaf peers.

### `topology/pub-complete`

Sent by each peer when its local collection ends — either all
locally-expected returns arrived or the peer's local job timeout
fired. One frame per peer per jid.

```python
{
    "cmd": "topology/pub-complete",
    "tag": "topology/pub-complete",
    "origin_cluster_id": <peer-cluster-id>,
    "session_generation": <int>,
    "load": {
        "jid":              <str>,
        "returned":         [<minion-id>, ...],   # subset of ack'd
        "missed":           [<minion-id>, ...],   # ack'd but no return
        "cancelled":        <bool>,
        "cancel_reason":    <str>|null,
        "topology": {
            "origin": <peer-cluster-id>,
            "path":   [<cluster-ids traversed>],
        },
    },
}
```

**Semantics**:

- `set(returned) ⊕ set(missed) == set(matched_minion_ids)` from the
  prior `pub-ack` for that jid. Enforced at originator; a peer that
  violates this gets a WARNING log + ack-set is trusted (fail-open).
- `cancelled` is True only if the peer received a `topology/jid-cancel`
  (deferred to Tier 2) or saw its parent peer master disappear
  mid-job. For a clean local-timeout the peer sets
  `cancelled: False` and populates `missed`.
- `pub-complete` carries no return payloads — those still flow as
  `topology/ret` with the per-minion return load. `pub-complete` is
  the metadata frame; `topology/ret` is the data frame.
- Fire-and-forget. If delivery to the originator fails (link
  down), the frame is dropped; the originator falls back to its own
  `--timeout` and reconstructs completion from `topology/ret`
  arrivals plus the prior `pub-ack`. Lossy by design — the frame is
  an optimization, not load-bearing.

### Health gating

Both frames are gated at `PeerMasterLink._assert_sendable`:

- `topology/pub-ack` → permitted only when `CONNECTED`. A peer in
  `QUIESCING` has stopped accepting publishes, so it cannot have an
  ack to send.
- `topology/pub-complete` → permitted on `CONNECTED` and `QUIESCING`,
  same as `topology/ret`. Returns drain through quiesce; completes
  must drain with them.

## Originator aggregation

The CLI's `LocalClient.get_cli_returns` already handles the "expected
set grows over time" case under `order_masters: True` with
`syndic_wait`. We extend the same algorithm:

```
expected_set        := publisher's own local matcher output
pub_ack_deadline    := now + topology_wait   (default 2.0s)
timeout_at          := now + opts["timeout"]

loop:
    drain pub-ack frames  → expected_set |= frame.matched_minion_ids
                            peers_acked.add(frame.origin_cluster_id)
    drain topology/ret    → returned_set |= frame.load["id"]
    drain pub-complete    → peers_complete.add(frame.origin_cluster_id)
                            missed_by_peer[frame.origin] = frame.missed

    if returned_set >= expected_set:
        break                                 # happy path: all back
    if peers_complete >= peers_acked and now > pub_ack_deadline:
        break                                 # every peer reported done
    if now > timeout_at:
        break                                 # global --timeout fires
```

Semantics vs. syndic:

- `topology_wait` only governs the window to collect `pub-ack`s
  (expected-set stabilization). Once all ack'd peers have sent
  `pub-complete`, the loop exits immediately — no need to wait
  `--timeout` just because one unresponsive minion didn't return.
  Syndic can't do this because syndics never signal done.
- `missed_by_peer` carries into the CLI's final output:
  minions that peers themselves could not reach are reported as
  distinct from minions the CLI couldn't reach. Operator sees
  "peer east-sub timed out on 2 of its minions" vs. "CLI never heard
  from east-sub" as different conditions.

## New opts

```yaml
# salt/config/__init__.py defaults
topology_wait: 2.0            # seconds; grace for pub-ack arrival
topology_pub_ack: true        # emit/consume pub-ack+pub-complete
topology_pub_complete_timeout: 60.0  # peer's local collection timeout
```

Default-on. Peers running without the opt (or older code) simply
don't send the frames; the originator's loop falls back to the
pre-RFC behavior (silence-based inference, bounded by `--timeout`).
No breaking change to mixed deployments.

## Rollout

1. **Phase 1 (land both frames, no CLI change)**: Add
   `topology/pub-ack` and `topology/pub-complete` to the dispatch
   table and `PeerMasterLink.send_pub_ack` / `send_pub_complete`
   senders. Originator discards the frames. Shippable alone; adds
   telemetry (operator can `grep /var/log/salt/master` for ack
   latency), no behavioral change.
2. **Phase 2 (opt-in originator consumption)**: Add
   `topology_wait` + consumer logic in `get_cli_returns`. Gated on
   `topology_pub_ack` opt; off-by-default initially.
3. **Phase 3 (flip default)**: After one release of real-world
   deployment, flip `topology_pub_ack` default to True. Document
   the mixed-deployment behavior (older peers = silent-mode
   fallback).

## Test plan

- **Unit** (`tests/pytests/unit/topology/`):
  - `test_pub_ack_sent_before_local_publish` — ack precedes
    `_publish_to_local_minions` dispatch.
  - `test_pub_ack_empty_match_list` — zero-match peer still acks.
  - `test_pub_complete_returned_plus_missed_equals_acked` —
    conservation invariant.
  - `test_pub_complete_dropped_on_link_down_does_not_block` —
    originator loop still terminates on `--timeout`.
- **Functional** (`tests/pytests/functional/topology/`):
  - `test_cli_sees_pub_ack_expected_set` — 3-peer flood;
    `expected_set` matches ∪ of per-peer matches.
  - `test_cli_terminates_on_pub_complete_before_timeout` — all
    peers ack+complete under 1s; CLI exits in <1s regardless of
    `--timeout`.
- **Scenario** (`tests/pytests/scenarios/topology/`):
  - `test_pub_ack_backward_compatible_with_silent_peer` — one peer
    older code (frames dropped), other peers new. CLI still works,
    falls back to silence-mode for the old peer.
- **Live-sandbox smoke** at
  `agents/scratch/topology-sandbox/`: fire
  `salt --timeout=30 '*' test.ping` from `topo-east`; grep master
  log for `pub-ack from topology-east-sub-sub-1 matched=2`; confirm
  CLI exits in <1s instead of the full 30s on the happy path.

## Open questions

- Should `pub-ack` carry `peer_estimated_rtt` for a future
  adaptive-timeout feature? Cheap to carry (one int), zero-cost to
  consumers that don't use it. **Recommend yes**: future-proof.
- Transit vs. leaf ack: a transit peer master that is itself
  forwarding to deeper peers — should it ack with its own matched
  set only, or
  also wait for deeper acks and roll them up? **Recommend own set
  only**: each peer acks for itself; the originator sees N acks for
  N peers in the flood. Rollup would centralize complexity in
  transits for no observable benefit.
- Signature on ack frames: reuse existing per-envelope AES signature
  from the session (already does this on all topology/* frames) —
  no new auth path.

## Non-adoption fallback

If this design is rejected, the alternative is to live with syndic's
original design and copy `syndic_wait` as `topology_wait`. That
closes 80% of the gap for 20% of the work but leaves the
"ambiguous completion window" permanently. The visualizer's
synthesized `job-complete` fallback becomes the de-facto
"done" signal, which is a weaker but functional story.
