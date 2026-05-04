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


def _is_blocking_publisher(pusher):
    """
    Return True when *pusher* is a real ``salt.transport`` ``PublishServer``
    whose ``publish`` is async-declared but synchronous under the hood
    (``SyncWrapper.send``).  Test fakes / mocks live in other modules and
    provide a truly async ``publish``, which can be awaited directly.
    """
    module = getattr(pusher.__class__, "__module__", "") or ""
    return module.startswith("salt.transport")


def _blocking_publish(pusher, raw):
    """
    Synchronous send wrapper used by :meth:`SaltPeer._send` via
    ``loop.run_in_executor``.

    Mirrors ``PublishServer.publish`` (lazy connect + ``pub_sock.send``) but
    runs in a worker thread so a slow or failing TCP connect cannot stall
    the asyncio event loop driving the rest of Raft.
    """
    if getattr(pusher, "pub_sock", None) is None:
        pusher.connect()
    pusher.pub_sock.send(raw)


class SaltPeer(Peer):
    """
    A ``Peer`` that sends Raft RPCs over the cluster pool channel.

    :param node_id:  The remote master's node-id (its ``opts["id"]``).
    :param pusher:   The ``PublishServer`` instance already connected to that
                     master's ``cluster_pool_port``.
    :param local_id: This master's own node-id (used as ``src`` in envelopes).
    :param voting:   Whether the peer counts toward quorum.
    """

    def __init__(self, node_id, pusher, local_id, voting=True):
        # Pass None for the node object; we manage node_id directly.
        super().__init__(None, node_id=node_id, voting=voting)
        self._pusher = pusher
        self._local_id = local_id

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
        raw = rpc.pack(tag, self._local_id, rpc_id, payload)
        try:
            if _is_blocking_publisher(self._pusher):
                # Real ``salt.transport`` ``PublishServer``: ``publish`` is
                # declared async but its body invokes synchronous
                # ``SyncWrapper.send``.  Awaiting it directly stalls the
                # asyncio event loop while the underlying TCP connect
                # retries — so one unreachable peer would starve heartbeats
                # to every other peer on the same loop.  Offload to the
                # default executor.
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _blocking_publish, self._pusher, raw)
            else:
                # Test fakes / mocks provide a truly async ``publish``.
                await self._pusher.publish(raw)
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
    alongside the existing pushers.

    :param node:      The local ``salt.cluster.consensus.raft.Node``.
    :param local_id:  This master's ``opts["id"]``.
    :param pushers:   Dict mapping peer node-id → ``PublishServer`` pusher.
    """

    def __init__(self, node, local_id, pushers):
        self._node = node
        self._local_id = local_id
        # pushers keyed by peer node-id for O(1) lookup
        self._pushers = pushers  # dict[str, PublishServer]

    async def _reply(self, dst, tag, payload):
        pusher = self._pushers.get(dst)
        if pusher is None:
            log.warning("RaftDispatcher: no pusher for %s, dropping %s reply", dst, tag)
            return
        raw = rpc.pack(tag, self._local_id, str(uuid.uuid4()), payload)
        try:
            await pusher.publish(raw)
        except Exception:  # pylint: disable=broad-except
            log.exception("RaftDispatcher: failed to send %s reply to %s", tag, dst)

    async def dispatch(self, tag, src, rpc_id, payload):
        """Route one inbound Raft RPC to the correct Node method."""
        node = self._node
        if node is None:
            log.debug("RaftDispatcher: node not ready, dropping %s", tag)
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
                )

            elif tag == rpc.INSTALL_SNAPSHOT_REPLY:
                node.install_snapshot_reply(payload["peer_id"], payload["our_term"])

            else:
                log.warning("RaftDispatcher: unhandled tag %s", tag)

        except Exception:  # pylint: disable=broad-except
            log.exception("RaftDispatcher: error handling %s from %s", tag, src)
