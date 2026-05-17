"""
Raft RPC wire layer for the Salt cluster channel.

Tags follow the existing ``cluster/raft/<kind>`` naming convention so they
are multiplexed over ``cluster_pool_port`` by ``handle_pool_publish`` in
``salt.channel.server.MasterPubServerChannel`` alongside the existing
``cluster/peer`` and ``cluster/event`` traffic.

Each Raft RPC is packed as a plain dict via ``salt.payload`` (msgpack) and
wrapped inside the event envelope understood by the pool puller:

    tag  : "cluster/raft/<kind>"
    data : {"src": <node_id>, "rpc_id": <str>,
            "raft_group_id": <str>, "payload": <dict>}

``raft_group_id`` identifies which Raft group the RPC belongs to so a
single master process can host multiple coexisting groups (the main
cluster group plus per-ring groups).  Older envelopes that pre-date
multi-ring support omit the field and are interpreted as the
``"cluster"`` group.
"""

import logging

import salt.payload
import salt.utils.event

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tag constants
# ---------------------------------------------------------------------------

REQUEST_VOTE = "cluster/raft/request-vote"
REQUEST_VOTE_REPLY = "cluster/raft/request-vote-reply"
PRE_REQUEST_VOTE = "cluster/raft/pre-request-vote"
PRE_REQUEST_VOTE_REPLY = "cluster/raft/pre-request-vote-reply"
APPEND_ENTRIES = "cluster/raft/append-entries"
APPEND_ENTRIES_REPLY = "cluster/raft/append-entries-reply"
INSTALL_SNAPSHOT = "cluster/raft/install-snapshot"
INSTALL_SNAPSHOT_REPLY = "cluster/raft/install-snapshot-reply"

ALL_TAGS = frozenset(
    {
        REQUEST_VOTE,
        REQUEST_VOTE_REPLY,
        PRE_REQUEST_VOTE,
        PRE_REQUEST_VOTE_REPLY,
        APPEND_ENTRIES,
        APPEND_ENTRIES_REPLY,
        INSTALL_SNAPSHOT,
        INSTALL_SNAPSHOT_REPLY,
    }
)


def is_raft_tag(tag):
    """Return True if *tag* is a Raft RPC tag we own."""
    return tag.startswith("cluster/raft/")


# ---------------------------------------------------------------------------
# Pack / unpack helpers
# ---------------------------------------------------------------------------


def pack(tag, src, rpc_id, payload, raft_group_id="cluster"):
    """
    Serialise a Raft RPC into the bytes the pool puller expects.

    :param tag:           One of the ``cluster/raft/*`` constants above.
    :param src:           Sender node-id (``opts["interface"]``) —
                          matches the cluster-wide identity used by
                          ``RaftService`` and the ``cluster_peers``
                          opt; not the daemon's ``opts["id"]``.
    :param rpc_id:        Opaque correlation string chosen by the
                          caller.
    :param payload:       Dict of RPC-specific fields.
    :param raft_group_id: Identifier of the Raft group this RPC
                          belongs to.  ``"cluster"`` (default) is the
                          main cluster group; named rings (e.g.
                          ``"jobs"``) get their own group ids.
    :returns:             Raw bytes ready for ``pusher.publish()``.
    """
    data = {
        "src": src,
        "rpc_id": rpc_id,
        "raft_group_id": raft_group_id,
        "payload": payload,
    }
    return salt.utils.event.SaltEvent.pack(tag, data)


def unpack(raw):
    """
    Deserialise raw bytes from the pool puller back into
    ``(tag, src, rpc_id, raft_group_id, payload)``.

    Envelopes that pre-date the multi-ring extension omit the
    ``raft_group_id`` field; those are interpreted as the main
    cluster group (``"cluster"``).

    :raises ValueError: if the envelope is missing required keys.
    """
    tag, data = salt.utils.event.SaltEvent.unpack(raw)
    try:
        return (
            tag,
            data["src"],
            data["rpc_id"],
            data.get("raft_group_id", "cluster"),
            data["payload"],
        )
    except KeyError as exc:
        raise ValueError(
            f"Malformed Raft RPC envelope (missing {exc}): {data!r}"
        ) from exc
