"""
Shared fixtures for functional consensus/raft tests.

These tests run entirely in-process: real ``Node`` objects, real asyncio,
real ``salt.utils.event`` framing — but with mock pushers instead of live TCP
connections to other masters.
"""

import asyncio
import collections

import pytest

from salt.cluster.consensus import rpc
from salt.cluster.consensus.peer import RaftDispatcher, SaltPeer
from salt.cluster.consensus.raft import ManualTimeoutScheduler, Node

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


class FakePusher:
    """
    Captures every ``publish(raw)`` call and can replay those bytes
    directly into the destination dispatcher — simulating the TCP hop.
    """

    def __init__(self):
        self.sent = collections.deque()

    async def publish(self, raw):
        self.sent.append(raw)


class ClusterNode:
    """
    One participant in an in-process Raft cluster.

    Holds:
      • a real ``Node`` (Raft state machine)
      • one ``FakePusher`` per peer (keyed by peer node-id)
      • a ``RaftDispatcher`` wired to those pushers
      • a ``ManualTimeoutScheduler`` (tick-driven, no wall-clock dependency)
    """

    def __init__(self, node_id, peer_ids):
        self.node_id = node_id
        self.peer_ids = peer_ids
        self.scheduler = ManualTimeoutScheduler()
        self.node = Node(node_id)
        self.node.register_schedule_timeout(self.scheduler.schedule)
        # one outbound pusher per peer
        self.pushers_out = {pid: FakePusher() for pid in peer_ids}
        # dispatcher reads inbound RPCs and sends replies via pushers_out
        self.dispatcher = RaftDispatcher(self.node, node_id, self.pushers_out)

    def make_salt_peers(self):
        """Return ``SaltPeer`` objects this node should use."""
        return [
            SaltPeer(pid, self.pushers_out[pid], self.node_id) for pid in self.peer_ids
        ]


def _build_cluster(node_ids):
    """
    Build a fully-connected in-process cluster.

    Returns a dict ``{node_id: ClusterNode}``.
    """
    peer_map = {nid: [other for other in node_ids if other != nid] for nid in node_ids}
    members = {nid: ClusterNode(nid, peer_map[nid]) for nid in node_ids}

    # Wire SaltPeer instances into each Node
    for nid, cn in members.items():
        cn.node.peers = cn.make_salt_peers()

    return members


async def _flush_tasks():
    """Yield control so that any pending asyncio tasks (from SaltPeer._fire) run."""
    await asyncio.sleep(0)
    await asyncio.sleep(0)


async def _deliver_all(members, rounds=8):
    """
    Drain outbound pushers: flush pending tasks, then for each byte sitting in
    a pusher destined for node B run it through B's dispatcher.  Repeat.
    """
    for _ in range(rounds):
        await _flush_tasks()
        delivered = False
        for src_id, cn in list(members.items()):
            for dst_id, pusher in list(cn.pushers_out.items()):
                if dst_id not in members:
                    continue
                while pusher.sent:
                    raw = pusher.sent.popleft()
                    try:
                        tag, s, rid, group, payload = rpc.unpack(raw)
                        await members[dst_id].dispatcher.dispatch(
                            tag, s, rid, payload, raft_group_id=group
                        )
                        delivered = True
                    except Exception:  # pylint: disable=broad-except
                        pass
        if not delivered:
            break


def _tick_all(members, advance=True):
    """Advance all schedulers to their next timeout and fire callbacks."""
    for cn in members.values():
        if advance:
            cn.scheduler.advance_clock_to_next_timeout()
        cn.scheduler.process_timeouts()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def three_node_ids():
    return ["master-1", "master-2", "master-3"]


@pytest.fixture
def cluster(three_node_ids):
    """Three-node in-process cluster, nodes started as followers."""
    members = _build_cluster(three_node_ids)
    for cn in members.values():
        cn.node.become_follower()
        # Expire last_followed so the first timeout fires an election immediately
        cn.node.last_followed = cn.node.get_now() - 10
    return members
