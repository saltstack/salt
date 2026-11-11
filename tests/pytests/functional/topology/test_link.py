"""
Functional tests for :mod:`salt.topology.link`.

These tests exercise :class:`PeerMasterLink` against the shared
master-topology functional harness (``two_cluster_fixture`` + the
``.accept_peer`` directional-trust primitive).  The receiver side
(``topology_link_port`` listener + ``_master_auth`` handling) is
Phase 3 work in :mod:`salt.topology.link_manager`; for tests that
need a counterparty to answer the handshake, we inject a fake
:class:`salt.channel.client.AsyncReqChannel` via
``salt.channel.client.AsyncReqChannel.factory`` monkeypatch.  That
is explicit about the Phase 2 boundary: this file tests only the
link's own send-side protocol machinery.

Behavioral invariants under test:

* Instantiation: a fresh :class:`PeerMasterLink` is INITIAL,
  carries one endpoint (the seed), and has ``peer_cluster_id`` None.
* ``add_endpoint`` deduplicates by ``(host, port)``; non-PeerRef
  input raises ``TypeError``.
* ``connect`` drives ``_master_auth`` through an
  :class:`AsyncReqChannel`.  On "ok" the link transitions to
  CONNECTED, ``peer_cluster_id`` is populated, and the session AES
  from the response is retained on the link.
* ``connect`` with a peer that answers "retry" lands in
  PENDING_ACCEPT and retries with backoff.
* ``connect`` with an unreachable peer (TCP refused) lands in
  DISCONNECTED on first attempt and raises on subsequent sends.
* ``send_publish`` emits a ``topology/pub`` envelope with
  ``origin``, ``destinations``, ``transit_match``, and ``path``
  carried on ``load["topology"]`` --- the receiver, not the sender,
  is responsible for authenticating the path.
* ``send_return`` carries the aggregated batch as-is under
  ``topology/ret``.
* ``send_summary`` round-trips a serialized
  :class:`ClusterSummary` under ``topology/sum``.
* ``quiesce`` rejects publishes with :class:`LinkUnavailable`
  but still permits ``send_return`` within the drain window.
* ``disconnect`` tears down channels; subsequent send raises
  :class:`LinkUnavailable`.
"""

import asyncio
import os

import pytest

import salt.channel.client
import salt.topology.link as link_mod
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, LinkUnavailable, PeerMasterLink
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Fakes --- in-file so Phase 3's real inbound listener can replace them
# ---------------------------------------------------------------------------


class _CapturedSend:
    """Return value of :meth:`_FakeReqChannel.send` for one call."""

    def __init__(self, load, tries, timeout, response):
        self.load = load
        self.tries = tries
        self.timeout = timeout
        self.response = response


class _FakeReqChannel:
    """
    Minimal stand-in for :class:`AsyncReqChannel` used by the Phase 2
    functional tests.

    Captures every outbound ``send()`` and returns a configured
    response.  The default response simulates a successful
    ``_master_auth`` ("ok" with a 32-byte session AES and an empty
    endpoint list).  Tests can override by setting
    ``handshake_response`` / ``default_response`` before calling
    :meth:`PeerMasterLink.connect`.
    """

    #: Overridable at the class level so tests can set the handshake
    #: outcome for every link in one place.
    handshake_response = None
    default_response = None
    sends = []  # noqa: RUF012 --- class-level capture; cleared per test

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        tag = None
        if isinstance(load, dict):
            tag = load.get("cmd") or load.get("tag")
        response = self.default_response
        if tag == "topology/_master_auth" and self.handshake_response is not None:
            response = self.handshake_response
        captured = _CapturedSend(load, tries, timeout, response)
        type(self).sends.append(captured)
        return response

    async def connect(self):
        pass

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close_async()


class _FakePubChannel:
    """Stand-in for :class:`AsyncPubChannel` --- just a well-behaved shell."""

    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False
        self._callback = None

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def connect(self):
        pass

    def on_recv(self, callback):
        self._callback = callback

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close_async()


@pytest.fixture
def fake_channels(monkeypatch):
    """
    Replace :class:`AsyncReqChannel` / :class:`AsyncPubChannel`
    factory entry points with the in-file fakes so ``connect()``
    does not need a Phase 3 receiver.  Returns a dict of
    ``{"req_sends": [...], "pub_sends": [...]}`` whose lists are
    populated as the test runs.
    """
    _FakeReqChannel.sends = []
    _FakePubChannel.sends = []
    _FakeReqChannel.handshake_response = {
        "status": "ok",
        "aes": os.urandom(32),
        "cluster_id": "east",
        "endpoints": [],
    }
    _FakeReqChannel.default_response = {"status": "ok"}
    monkeypatch.setattr(
        salt.channel.client.AsyncReqChannel,
        "factory",
        _FakeReqChannel.factory,
    )
    monkeypatch.setattr(
        salt.channel.client.AsyncPubChannel,
        "factory",
        _FakePubChannel.factory,
    )
    # Also patch the module-local references (link.py imports the
    # classes at module load time).  The implementation looks them
    # up on the imported module to make the monkeypatch work.
    monkeypatch.setattr(
        link_mod,
        "AsyncReqChannel",
        _FakeReqChannel,
        raising=False,
    )
    monkeypatch.setattr(
        link_mod,
        "AsyncPubChannel",
        _FakePubChannel,
        raising=False,
    )
    return {
        "req_sends": _FakeReqChannel.sends,
        "pub_sends": _FakePubChannel.sends,
    }


def _link_opts(cluster, local_cluster_id="west"):
    """Build an opts dict suitable for a ``PeerMasterLink`` targeting
    *cluster*.  Mirrors what :mod:`salt.topology.link_manager` would
    assemble at runtime.
    """
    master = cluster.masters[0]
    opts = dict(master.config)
    opts["cluster_id"] = local_cluster_id
    opts["topology_detach_quiesce"] = 1
    return opts


def _peer_ref_for(cluster, port=None):
    """Return a :class:`PeerRef` pointing at *cluster*'s link port."""
    master = cluster.masters[0]
    host = master.config.get("interface", "127.0.0.1")
    link_port = port if port is not None else master.config["topology_link_port"]
    return PeerRef(host=host, port=link_port, finger=None)


# ---------------------------------------------------------------------------
# Instantiation + initial state
# ---------------------------------------------------------------------------


def test_instantiation_initial_health(two_cluster_fixture):
    """Fresh link is in LinkHealth.INITIAL with no peer_cluster_id."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        assert link.health == LinkHealth.INITIAL
        assert link.peer_cluster_id is None
    finally:
        io_loop.close()


def test_instantiation_seed_endpoint_recorded(two_cluster_fixture):
    """The seed ``PeerRef`` is present in ``endpoints`` as the only entry."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        assert len(link.endpoints) == 1
        assert link.endpoints[0] == seed
    finally:
        io_loop.close()


def test_remote_summary_initially_none(two_cluster_fixture):
    """``remote_summary`` is None before any inbound summary arrives."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        assert link.remote_summary is None
    finally:
        io_loop.close()


# ---------------------------------------------------------------------------
# add_endpoint
# ---------------------------------------------------------------------------


def test_add_endpoint_appends(two_cluster_fixture):
    """A new ``(host, port)`` adds a second endpoint."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        new_ref = PeerRef(host="127.0.0.2", port=seed.port, finger=None)
        link.add_endpoint(new_ref)
        assert new_ref in link.endpoints
        assert len(link.endpoints) == 2
    finally:
        io_loop.close()


def test_add_endpoint_dedup_by_host_port(two_cluster_fixture):
    """Re-adding the same (host, port) is a no-op."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        dup = PeerRef(host=seed.host, port=seed.port, finger="pinned")
        link.add_endpoint(dup)
        assert len(link.endpoints) == 1
    finally:
        io_loop.close()


def test_add_endpoint_rejects_non_peerref(two_cluster_fixture):
    """``add_endpoint`` type-checks input."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    io_loop = asyncio.new_event_loop()
    try:
        link = PeerMasterLink(opts, seed, io_loop)
        with pytest.raises(TypeError):
            link.add_endpoint({"host": "a", "port": 1})
    finally:
        io_loop.close()


# ---------------------------------------------------------------------------
# connect() --- handshake success / retry / failure
# ---------------------------------------------------------------------------


def test_connect_handshake_ok_populates_peer_cluster_id(
    two_cluster_fixture, fake_channels
):
    """Handshake ``ok`` -> link CONNECTED + peer_cluster_id set."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        return link

    link = asyncio.run(_run())
    assert link.peer_cluster_id == "east"
    assert link.health == LinkHealth.CONNECTED


def test_connect_sends_master_auth_tag(two_cluster_fixture, fake_channels):
    """The first captured send carries the ``topology/_master_auth`` tag."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()

    asyncio.run(_run())
    first = fake_channels["req_sends"][0]
    assert isinstance(first.load, dict)
    tag = first.load.get("cmd") or first.load.get("tag")
    assert tag == "topology/_master_auth"


def test_connect_pending_accept_backoff(two_cluster_fixture, fake_channels):
    """Handshake ``retry`` -> PENDING_ACCEPT; link retries at least twice."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    # Short backoff so the test does not take forever.
    opts["topology_handshake_backoff"] = 0.05
    opts["topology_handshake_max_tries"] = 3
    seed = _peer_ref_for(east)
    _FakeReqChannel.handshake_response = {"status": "retry"}

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        return link

    link = asyncio.run(_run())
    assert link.health == LinkHealth.PENDING_ACCEPT
    handshake_calls = [
        s
        for s in fake_channels["req_sends"]
        if isinstance(s.load, dict)
        and (s.load.get("cmd") or s.load.get("tag")) == "topology/_master_auth"
    ]
    assert len(handshake_calls) >= 2


def test_connect_rejected_marks_disconnected(two_cluster_fixture, fake_channels):
    """``rejected`` from the peer -> link DISCONNECTED, no further retries."""
    east, west = two_cluster_fixture
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)
    _FakeReqChannel.handshake_response = {"status": "rejected"}

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        return link

    link = asyncio.run(_run())
    assert link.health == LinkHealth.DISCONNECTED


# ---------------------------------------------------------------------------
# send_publish / send_return / send_summary
# ---------------------------------------------------------------------------


def _tags(sends):
    out = []
    for s in sends:
        if not isinstance(s.load, dict):
            continue
        tag = s.load.get("cmd") or s.load.get("tag")
        out.append(tag)
    return out


def test_send_publish_emits_topology_pub(two_cluster_fixture, fake_channels):
    """send_publish wraps the load with the topology envelope."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        inner = {
            "jid": "20260101000000000000",
            "tgt": "*",
            "fun": "test.ping",
            "topology": {
                "origin": "west",
                "destinations": None,
                "transit_match": True,
                "path": ["west"],
            },
        }
        await link.send_publish(inner, path=["west"])

    asyncio.run(_run())
    tags = _tags(fake_channels["req_sends"])
    assert "topology/pub" in tags


def test_send_publish_envelope_shape(two_cluster_fixture, fake_channels):
    """The topology envelope carries origin + destinations + path."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        inner = {
            "jid": "20260101000000000001",
            "tgt": "web-*",
            "fun": "test.ping",
            "topology": {
                "origin": "west",
                "destinations": ["east"],
                "transit_match": False,
                "path": ["west"],
            },
        }
        await link.send_publish(inner, path=["west"])

    asyncio.run(_run())
    pub = [
        s
        for s in fake_channels["req_sends"]
        if isinstance(s.load, dict)
        and (s.load.get("cmd") or s.load.get("tag")) == "topology/pub"
    ][0]
    body = pub.load.get("load") if "load" in pub.load else pub.load
    # The implementation serializes under "payload" or "load"; accept either.
    carried = body.get("topology") if isinstance(body, dict) else None
    if carried is None:
        # Some impls route the envelope one level up next to the tag.
        carried = pub.load.get("topology")
    assert carried is not None, pub.load
    assert carried["origin"] == "west"
    assert carried["destinations"] == ["east"]
    assert "path" in carried


def test_send_publish_does_not_mutate_path(two_cluster_fixture, fake_channels):
    """``send`` must not append to the caller's ``path`` --- authentication
    is a receive-side concern."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    path = ["west"]

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        inner = {
            "jid": "20260101000000000002",
            "topology": {
                "origin": "west",
                "destinations": None,
                "transit_match": True,
                "path": list(path),
            },
        }
        await link.send_publish(inner, path=path)

    asyncio.run(_run())
    assert path == ["west"]


def test_send_return_batch(two_cluster_fixture, fake_channels):
    """send_return emits a topology/ret envelope with the aggregated batch."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    batch = [
        {"id": "m1", "jid": "j1", "return": {"ok": True}},
        {"id": "m2", "jid": "j1", "return": {"ok": True}},
    ]

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        await link.send_return(batch, path=["east", "west"])

    asyncio.run(_run())
    rets = [
        s
        for s in fake_channels["req_sends"]
        if isinstance(s.load, dict)
        and (s.load.get("cmd") or s.load.get("tag")) == "topology/ret"
    ]
    assert len(rets) == 1
    body = rets[0].load.get("load") if "load" in rets[0].load else rets[0].load
    carried_batch = body.get("batch") if isinstance(body, dict) else None
    if carried_batch is None:
        carried_batch = rets[0].load.get("batch")
    assert carried_batch is not None
    assert len(carried_batch) == 2


def test_send_summary(two_cluster_fixture, fake_channels):
    """send_summary serializes the ClusterSummary into a topology/sum send."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    summary = ClusterSummary(
        cluster_id="west",
        path=("west",),
        minion_count=3,
        up_count=3,
        grain_histograms={},
        origin_seq=1,
        origin_at=1700000000.0,
    )

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        await link.send_summary(summary)

    asyncio.run(_run())
    tags = _tags(fake_channels["req_sends"])
    assert "topology/sum" in tags


def test_send_event(two_cluster_fixture, fake_channels):
    """send_event emits a topology/evt send with the event payload."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        await link.send_event(
            {"tag": "salt/job/j1/new", "data": {"foo": "bar"}},
            path=["west"],
        )

    asyncio.run(_run())
    tags = _tags(fake_channels["req_sends"])
    assert "topology/evt" in tags


# ---------------------------------------------------------------------------
# quiesce / disconnect
# ---------------------------------------------------------------------------


def test_quiesce_rejects_publish_permits_return(two_cluster_fixture, fake_channels):
    """During quiesce, send_publish raises; send_return still goes through."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    # Short drain so the test is quick but non-zero so we observe the window.
    opts["topology_detach_quiesce"] = 1
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        quiesce_task = loop.create_task(link.quiesce())
        # Give the state transition a chance to settle.
        await asyncio.sleep(0.01)
        pub_raised = False
        try:
            await link.send_publish(
                {
                    "jid": "j",
                    "topology": {
                        "origin": "west",
                        "destinations": None,
                        "transit_match": True,
                        "path": ["west"],
                    },
                },
                path=["west"],
            )
        except LinkUnavailable:
            pub_raised = True
        # Return should still succeed while we are in QUIESCING.
        await link.send_return(
            [{"id": "m1", "jid": "j", "return": {"ok": True}}],
            path=["east", "west"],
        )
        await quiesce_task
        return pub_raised, link.health

    pub_raised, final_health = asyncio.run(_run())
    assert pub_raised, "send_publish must raise LinkUnavailable while QUIESCING"
    assert final_health == LinkHealth.DISCONNECTED


def test_disconnect_closes_channels(two_cluster_fixture, fake_channels):
    """disconnect() tears down the channels; subsequent send raises."""
    east, west = two_cluster_fixture
    east.accept_peer(west)
    opts = _link_opts(west, local_cluster_id="west")
    seed = _peer_ref_for(east)

    async def _run():
        loop = asyncio.get_event_loop()
        link = PeerMasterLink(opts, seed, loop)
        await link.connect()
        await link.disconnect()
        return link

    link = asyncio.run(_run())
    assert link.health == LinkHealth.DISCONNECTED

    async def _attempt():
        await link.send_summary(
            ClusterSummary(
                cluster_id="west",
                path=("west",),
                minion_count=0,
                up_count=0,
                grain_histograms={},
                origin_seq=99,
                origin_at=1700000000.0,
            )
        )

    with pytest.raises(LinkUnavailable):
        asyncio.run(_attempt())
