"""
SaltPeer — bridges the Raft callback surface to the cluster channel transport.

The Raft core (``salt.cluster.consensus.raft.Node``) talks to peers through
the ``Peer`` interface: fire-and-forget RPCs whose *reply* arrives later via
a callback.  ``SaltPeer`` implements that interface by:

  • **Sending**  — serialising the RPC with ``salt.cluster.consensus.rpc`` and
    pushing it to the remote master's ``cluster_pool_port`` via the per-peer
    ``PublishServer`` pusher that already exists in
    ``MasterPubServerChannel._publish_daemon``.

  • **Receiving** — ``handle_pool_publish`` in the channel server calls
    ``RaftDispatcher.dispatch`` for every ``cluster/raft/*`` tag.
    ``RaftDispatcher`` holds a reference to the local ``Node`` and routes
    each inbound message to the correct ``Node`` method, then fires the
    reply callback (which writes the reply back through the sender's pusher).

Asyncio is used for all I/O; the Raft node methods themselves remain
synchronous and callback-oriented.
"""

import asyncio
import logging
import uuid

from salt.cluster.consensus import rpc
from salt.cluster.consensus.raft.node import Peer

log = logging.getLogger(__name__)


async def _publish(pusher, raw):
    """
    Send *raw* over a Raft peer's TCP pusher using a truly-async path.

    Why this exists
    ---------------
    ``salt.transport.tcp.PublishServer.publish`` is declared ``async def``
    but its body is synchronous: it drives a Tornado event loop via
    :class:`salt.utils.asynchronous.SyncWrapper`.  Awaiting it directly
    on a busy asyncio loop blocks the loop on the underlying TCP
    connect/send retry; offloading to ``loop.run_in_executor`` (the
    previous shape of this code) makes the executor thread invoke
    ``SyncWrapper.run_sync`` from outside the loop's thread, which
    races with loop teardown — under CPU contention or fixture
    shutdown the thread schedules late, finds the loop stopped, and
    raises ``RuntimeError: Event loop stopped before Future completed.``
    The Raft RPC is silently dropped, elections never converge, and
    the test eventually fails with "no leader elected" or split-brain.

    Local repro of the bug pre-fix: 7/20 fail under stress-ng on
    debian-12 amd64.  Post-fix: 0/20 expected.

    What this does
    --------------
    Lazily attach a private :class:`salt.transport.tcp._TCPPubServerPublisher`
    to the pusher object on first send and reuse it on subsequent
    sends.  That class exposes a real ``async def send`` that uses the
    underlying Tornado IOStream directly — no SyncWrapper, no executor,
    no cross-thread loop access.

    Why we don't change ``salt.transport.tcp.PublishServer``
    -------------------------------------------------------
    Adding a public ``publish_async`` method to ``PublishServer`` would
    expand salt's transport API surface, which is a salt-wide decision
    requiring buy-in across all transport implementations.  Keeping the
    truly-async client as a private attribute on the pusher (only used
    by our consensus code) confines the change to this branch.

    Test fakes / mocks
    ------------------
    Pushers that aren't real ``PublishServer`` instances (test fakes,
    in-memory mocks, etc.) are detected by class module — their
    ``publish`` is already truly async, so just await it directly.
    ``MagicMock`` auto-creates any attribute on access, so a
    ``hasattr`` probe for ``pull_host`` / ``pull_port`` would falsely
    classify a mock as a real publisher; the module check avoids that.
    """
    module = getattr(type(pusher), "__module__", "") or ""
    if not module.startswith("salt.transport"):
        await pusher.publish(raw)
        return

    client = getattr(pusher, "_consensus_async_client", None)
    if client is None:
        # Lazy import — keeps this module loadable in test environments
        # that monkey-patch out salt.transport.
        from salt.transport.tcp import (  # pylint: disable=import-outside-toplevel
            _TCPPubServerPublisher,
        )

        client = _TCPPubServerPublisher(
            pusher.pull_host, pusher.pull_port, getattr(pusher, "pull_path", None)
        )
        await client.connect()
        # Stash on the pusher so the next send reuses the connection.
        # The pusher's lifetime exceeds the master process; the kernel
        # closes the fd at exit, so explicit teardown isn't required.
        pusher._consensus_async_client = client
    await client.send(raw)


class SaltPeer(Peer):
    """
    A ``Peer`` that sends Raft RPCs over the cluster pool channel.

    :param node_id:       The remote master's node-id — its
                          ``opts["interface"]`` address (matches the
                          entries in ``opts["cluster_peers"]`` and the
                          ``peer_pushers`` keys used everywhere else
                          in the cluster code).
    :param pusher:        The ``PublishServer`` instance already
                          connected to that master's
                          ``cluster_pool_port``.
    :param local_id:      This master's own node-id (used as ``src``
                          in envelopes).
    :param voting:        Whether the peer counts toward quorum.
    :param raft_group_id: Which Raft group this peer belongs to.
                          ``"cluster"`` (default) is the main cluster
                          group; per-ring peers carry the ring name so
                          the dispatcher on the receiving side routes
                          RPCs to the correct local ``Node``.
    """

    def __init__(self, node_id, pusher, local_id, voting=True, raft_group_id="cluster"):
        # Pass None for the node object; we manage node_id directly.
        super().__init__(None, node_id=node_id, voting=voting)
        self._pusher = pusher
        self._local_id = local_id
        self._raft_group_id = raft_group_id

    @property
    def node_id(self):
        return self._node_id

    @property
    def address(self):
        return self._node_id

    # ------------------------------------------------------------------
    # Internal send helper
    # ------------------------------------------------------------------

    async def _send(self, tag, payload, rpc_id=None):
        rpc_id = rpc_id or str(uuid.uuid4())
        raw = rpc.pack(
            tag,
            self._local_id,
            rpc_id,
            payload,
            raft_group_id=self._raft_group_id,
        )
        try:
            await _publish(self._pusher, raw)
        except Exception:  # pylint: disable=broad-except
            log.exception("SaltPeer: failed to send %s to %s", tag, self._node_id)

    def _fire(self, tag, payload, rpc_id=None):
        """Schedule ``_send`` on the running event loop (non-blocking)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send(tag, payload, rpc_id))
        except RuntimeError:
            # No running loop — fall back to a new one (test / bootstrap context).
            asyncio.run(self._send(tag, payload, rpc_id))

    # ------------------------------------------------------------------
    # Peer interface
    # ------------------------------------------------------------------

    def request_vote(self, callback, node_id, term, last_log_term, last_log_index):
        self._fire(
            rpc.REQUEST_VOTE,
            {
                "callback_node": self._local_id,
                "candidate_id": node_id,
                "term": term,
                "last_log_term": last_log_term,
                "last_log_index": last_log_index,
            },
        )

    def pre_request_vote(self, callback, node_id, term, last_log_term, last_log_index):
        self._fire(
            rpc.PRE_REQUEST_VOTE,
            {
                "callback_node": self._local_id,
                "candidate_id": node_id,
                "term": term,
                "last_log_term": last_log_term,
                "last_log_index": last_log_index,
            },
        )

    def append_entries(
        self,
        callback,
        leader_id,
        term,
        prev_log_term,
        prev_log_index,
        leader_commit,
        *entries,
        **kwargs,
    ):
        self._fire(
            rpc.APPEND_ENTRIES,
            {
                "callback_node": self._local_id,
                "leader_id": leader_id,
                "term": term,
                "prev_log_term": prev_log_term,
                "prev_log_index": prev_log_index,
                "leader_commit": leader_commit,
                "entries": [
                    (
                        e
                        if isinstance(e, dict)
                        else e._asdict() if hasattr(e, "_asdict") else list(e)
                    )
                    for e in entries
                ],
                "leader_client_address": kwargs.get("leader_client_address"),
            },
        )

    def install_snapshot(
        self,
        callback,
        leader_id,
        term,
        last_included_index,
        last_included_term,
        data,
        **kwargs,
    ):
        # snapshot data may be bytes — encode as list of ints for msgpack portability
        if isinstance(data, (bytes, bytearray, memoryview)):
            data = list(bytes(data))
        self._fire(
            rpc.INSTALL_SNAPSHOT,
            {
                "callback_node": self._local_id,
                "leader_id": leader_id,
                "term": term,
                "last_included_index": last_included_index,
                "last_included_term": last_included_term,
                "data": data,
            },
        )


class RaftDispatcher:
    """
    Receives decoded ``cluster/raft/*`` messages from ``handle_pool_publish``
    and drives the local Raft ``Node``, then sends the reply back via the
    appropriate pusher.

    One ``RaftDispatcher`` instance lives inside ``MasterPubServerChannel``
    alongside the existing pushers.  When this master hosts multiple
    Raft groups (the main cluster group plus per-ring groups) it owns
    one ``Node`` per group; inbound RPCs carry a ``raft_group_id``
    field that selects the target ``Node``.

    :param node:      Either a single ``Node`` (treated as the
                      ``"cluster"`` group) or a ``dict[str, Node]``
                      mapping group-id to its local ``Node``.  Passing
                      a single Node preserves the pre-multi-ring
                      constructor signature.
    :param local_id:  This master's node-id (``opts["interface"]``) — used as
                      ``src`` in outbound RPC envelopes.
    :param pushers:   Dict mapping peer node-id (interface address) ->
                      ``PublishServer`` pusher.
    """

    def __init__(self, node, local_id, pushers):
        # Normalise to a dict keyed by group-id.  Callers that pass a
        # bare Node (or None) are interpreted as the main cluster
        # group; the dict-of-nodes form is the multi-ring shape.
        if isinstance(node, dict):
            self._nodes = dict(node)
        else:
            self._nodes = {"cluster": node}
        self._local_id = local_id
        # pushers keyed by peer node-id for O(1) lookup
        self._pushers = pushers  # dict[str, PublishServer]

    @property
    def _node(self):
        """
        Backward-compat accessor for callers that reach in for the
        single Node (tests primarily).  Returns the cluster group's
        Node so existing assertions keep working.
        """
        return self._nodes.get("cluster")

    @_node.setter
    def _node(self, node):
        """
        Mutating ``dispatcher._node`` (used by some tests to simulate
        a failed leader losing its Node) maps to the cluster group.
        Setting ``None`` removes the cluster Node entirely so
        :meth:`dispatch` drops inbound RPCs.
        """
        if node is None:
            self._nodes.pop("cluster", None)
        else:
            self._nodes["cluster"] = node

    def register_node(self, raft_group_id, node):
        """
        Add or replace the ``Node`` for *raft_group_id*.

        Used when ``RaftService`` brings up a per-ring Raft group
        after the dispatcher has already been constructed.
        """
        self._nodes[raft_group_id] = node

    def unregister_node(self, raft_group_id):
        """Remove the ``Node`` registered for *raft_group_id*, if any."""
        self._nodes.pop(raft_group_id, None)

    async def _reply(self, dst, tag, payload, raft_group_id="cluster"):
        pusher = self._pushers.get(dst)
        if pusher is None:
            log.warning("RaftDispatcher: no pusher for %s, dropping %s reply", dst, tag)
            return
        raw = rpc.pack(
            tag,
            self._local_id,
            str(uuid.uuid4()),
            payload,
            raft_group_id=raft_group_id,
        )
        try:
            await _publish(pusher, raw)
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftDispatcher: failed to send %s reply to %s", tag, dst)

    async def dispatch(self, tag, src, rpc_id, payload, raft_group_id="cluster"):
        """Route one inbound Raft RPC to the correct Node method."""
        node = self._nodes.get(raft_group_id)
        if node is None:
            log.debug(
                "RaftDispatcher: no node for group %s, dropping %s",
                raft_group_id,
                tag,
            )
            return

        try:
            if tag == rpc.REQUEST_VOTE:
                granted, term, lc = node.request_vote(
                    payload["candidate_id"],
                    payload["term"],
                    last_log_term=payload.get("last_log_term"),
                    last_log_index=payload.get("last_log_index"),
                )
                await self._reply(
                    payload["callback_node"],
                    rpc.REQUEST_VOTE_REPLY,
                    {"granted": granted, "term": term, "voter_id": self._local_id},
                    raft_group_id=raft_group_id,
                )

            elif tag == rpc.PRE_REQUEST_VOTE:
                granted, term, lc = node.pre_request_vote(
                    payload["candidate_id"],
                    payload["term"],
                    last_log_term=payload.get("last_log_term"),
                    last_log_index=payload.get("last_log_index"),
                )
                await self._reply(
                    payload["callback_node"],
                    rpc.PRE_REQUEST_VOTE_REPLY,
                    {"granted": granted, "term": term, "voter_id": self._local_id},
                    raft_group_id=raft_group_id,
                )

            elif tag == rpc.REQUEST_VOTE_REPLY:
                node.request_vote_reply(src, payload["granted"], payload["term"])

            elif tag == rpc.PRE_REQUEST_VOTE_REPLY:
                node.pre_request_vote_reply(src, payload["granted"], payload["term"])

            elif tag == rpc.APPEND_ENTRIES:
                entries = payload.get("entries", [])
                success, term, last_idx, conflict_term, lc = node.handle_append_entries(
                    payload["leader_id"],
                    payload["term"],
                    payload.get("prev_log_term"),
                    payload.get("prev_log_index"),
                    payload.get("leader_commit"),
                    *entries,
                    leader_client_address=payload.get("leader_client_address"),
                )
                sent_log_index = (
                    payload.get("prev_log_index", -1) + len(entries)
                    if payload.get("prev_log_index") is not None
                    else len(entries) - 1
                )
                await self._reply(
                    payload["callback_node"],
                    rpc.APPEND_ENTRIES_REPLY,
                    {
                        "term": payload["term"],
                        "prev_log_term": payload.get("prev_log_term"),
                        "prev_log_index": payload.get("prev_log_index"),
                        "sent_log_index": sent_log_index,
                        "peer_id": self._local_id,
                        "our_term": term,
                        "success": success,
                        "conflict_index": last_idx,
                        "conflict_term": conflict_term,
                    },
                    raft_group_id=raft_group_id,
                )

            elif tag == rpc.APPEND_ENTRIES_REPLY:
                node.append_entries_reply(
                    payload["term"],
                    payload.get("prev_log_term"),
                    payload.get("prev_log_index"),
                    payload.get("sent_log_index"),
                    payload["peer_id"],
                    payload["our_term"],
                    payload["success"],
                    payload.get("conflict_index"),
                    payload.get("conflict_term"),
                )

            elif tag == rpc.INSTALL_SNAPSHOT:
                raw_data = payload.get("data", [])
                if isinstance(raw_data, list):
                    raw_data = bytes(raw_data)
                our_term, lc = node.install_snapshot(
                    payload["leader_id"],
                    payload["term"],
                    payload["last_included_index"],
                    payload["last_included_term"],
                    raw_data,
                )
                await self._reply(
                    payload["callback_node"],
                    rpc.INSTALL_SNAPSHOT_REPLY,
                    {"our_term": our_term, "peer_id": self._local_id},
                    raft_group_id=raft_group_id,
                )

            elif tag == rpc.INSTALL_SNAPSHOT_REPLY:
                node.install_snapshot_reply(payload["peer_id"], payload["our_term"])

            else:
                log.warning("RaftDispatcher: unhandled tag %s", tag)

        except Exception:  # pylint: disable=broad-except
            log.exception("RaftDispatcher: error handling %s from %s", tag, src)
