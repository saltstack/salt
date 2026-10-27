"""
Load-stress for the MWorker -> publish-daemon topology-return hand-off.

Per RFC item 4 (``rfcs/master-topology.md`` -> *Implementation
follow-ups* -> *MWorker->publish-daemon return hand-off durability*):

    Current design fires ``salt/topology/return/<jid>`` on the event
    bus, which is pub-sub (unordered, lossy under backpressure).  If
    load testing shows return loss on burst, replace with a persistent
    bounded queue (either a dedicated MmapCache keyed by jid, or a
    filesystem spool), reading in the publish daemon's subscriber loop.

This test drives the exact wire path the production hand-off uses:

* The MWorker fires ``salt/topology/return/<origin>/<jid>`` via
  ``self.event.fire_event(data, tag)`` in
  :meth:`salt.master.AESFuncs._maybe_fire_topology_return`, which
  frames the payload with ``frame_msg_ipc`` and writes it to EP's
  pull socket.
* The publish daemon's topology event subscriber reads from EP's
  pub socket.

We stand EP up as its own subprocess (via the existing
``ep`` fixture under this directory), bang N framed topology-return
payloads at the pull socket, and verify the pub-socket subscriber
sees all N -- any gap is a drop in the hand-off path.

Pass criterion: zero drops at 1000 returns/sec sustained for 10
seconds (10_000 payloads).  Observing any drops here would flip the
decision in favour of implementing the persistent-queue variant
described in the RFC.

The test is parked under ``tests/pytests/stress`` so it runs only
on the explicit stress-test invocation (same gate used by the EP
throughput floor, fanout, and churn tests in this directory).  CI
is not expected to drive it on every PR; it is a measurement tool.
"""

from __future__ import annotations

import time

import pytest

import salt.utils.msgpack

from .test_ep_stress import (  # pylint: disable=relative-beyond-top-level
    _connect_subscriber,
    _make_event,
    _SyncPuller,
    _wait_for,
)


@pytest.mark.timeout(120)
def test_topology_return_handoff_zero_drops_at_1000_per_sec(ep):
    """
    Fire 10_000 ``salt/topology/return/east/<jid>`` events at EP as
    fast as a single blocking sender can push frames; the subscriber
    must receive every one with no gap.  Any drop here means the
    event-bus hand-off cannot be relied on for return durability and
    the RFC's persistent-queue variant must be implemented.
    """
    n = 10_000
    target_rate = 1000  # returns per second (sustained)
    tag_prefix = "salt/topology/return/east/"

    sub = _connect_subscriber(ep.pub_path)
    assert _wait_for(ep.is_alive, timeout=2.0)

    puller = _SyncPuller(ep.pull_path)
    t_start = time.monotonic()
    for i in range(n):
        tag = f"{tag_prefix}{i:020d}"
        payload = {
            "load": {
                "jid": f"{i:020d}",
                "id": f"minion-{i % 100}",
                "return": {"ret": "ok"},
                "topology": {"origin": "east"},
            }
        }
        puller.send(_make_event(tag, payload))
    send_elapsed = time.monotonic() - t_start

    # Drain with generous deadline: at 1000/s the test should finish
    # in ~10s; give 60s to swallow any pytest / scheduler jitter.
    received = sub.drain(n, timeout=60.0)
    total_elapsed = time.monotonic() - t_start
    rate = n / total_elapsed

    puller.close()
    sub.close()
    assert ep.is_alive(), "EP died under topology-return load"

    # Correctness: no drops.  Pull indices out of each payload and
    # verify a dense 0..n-1 sequence.
    idxs = []
    for msg in received:
        raw = msg.encode() if isinstance(msg, str) else bytes(msg)
        _tag_bytes, _sep, mdata = raw.partition(b"\n\n")
        parsed = salt.utils.msgpack.unpackb(mdata, raw=False)
        inner = parsed["load"]
        idxs.append(int(inner["jid"]))
    missing = set(range(n)) - set(idxs)
    duplicate = len(idxs) - len(set(idxs))
    drop_rate = len(missing) / n

    assert not missing, (
        f"topology-return hand-off dropped {len(missing)}/{n} payloads "
        f"({drop_rate*100:.4f}%); send={send_elapsed:.2f}s "
        f"total={total_elapsed:.2f}s rate={rate:.1f}/s; "
        f"RFC says: implement persistent queue."
    )
    assert duplicate == 0, (
        f"topology-return hand-off duplicated {duplicate} payloads; "
        f"event-bus ordering guarantee violated."
    )

    # Rate floor: assert we actually sustained >= target_rate; if the
    # bus throttled us below 1000/s we are not stress-testing what we
    # claim to be stress-testing.
    assert rate >= target_rate, (
        f"EP throughput {rate:.1f} evt/s below target {target_rate}/s "
        f"({send_elapsed:.2f}s send, {total_elapsed:.2f}s total); "
        f"test did not actually exercise the burst-load regime."
    )
