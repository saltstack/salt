"""
Functional tests for :mod:`salt.topology.link_manager`.

These tests exercise the process-wide link-manager state and
lifecycle against the real :mod:`salt.topology.registry` and
:mod:`salt.topology.breadcrumbs` MmapCaches on disk.  No mocks of
our own topology modules (router, registry, breadcrumbs, link,
migration) --- fakes are only used in place of
:class:`salt.channel.client.AsyncReqChannel` / ``AsyncPubChannel``
so handshake flows do not require a Phase 3 receiver.

Coverage
--------
* ``pre_fork`` materialises the mmap files, reserves the
  ``topology_link_port`` socket, and does NOT populate module
  globals.
* ``start`` wires :func:`salt.topology.router.get_router` with a
  :class:`TopologyRouter`; the dispatch tag table is populated.
* ``start`` idempotency: a second call without ``stop`` is a
  warned no-op.
* Owner-PID guard: ``add_link`` from a forked child raises
  :exc:`RuntimeError`.
* ``_handle_master_auth``: first-contact writes to
  ``masters_pre/`` and replies ``retry``; accepted replies ``ok``
  with session AES + endpoints; rejected (in masters_rejected/)
  replies ``rejected``; reserved cluster_id replies ``rejected``.
* ``_handle_inbound`` dispatches each tag to the matching router
  method; bad session is dropped with WARNING.
* ``stop`` closes the listener and clears every registry.
* End-to-end two-master handshake via ``two_cluster_fixture``:
  east.start / west.start / west.accept_peer(east) /
  east._handle_master_auth sees west's attempt and returns ``ok``.
"""

import asyncio
import logging
import multiprocessing
import os
import socket

import pytest

import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod
import salt.utils.files
import salt.utils.yaml
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows,  # fork(2) + fcntl.FD_CLOEXEC
]


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fakes for the channel-client layer
# ---------------------------------------------------------------------------


class _FakeReqChannel:
    """Minimal AsyncReqChannel replacement for link.connect() flows."""

    handshake_response = None
    default_response = None
    sends = []  # noqa: RUF012

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self._closed = False

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def send(self, load, tries=None, timeout=None, raw=False):
        type(self).sends.append(load)
        tag = None
        if isinstance(load, dict):
            tag = load.get("cmd") or load.get("tag")
        if tag == "topology/_master_auth" and self.handshake_response is not None:
            return self.handshake_response
        return self.default_response

    async def connect(self):
        pass

    def close(self):
        self._closed = True

    async def close_async(self):
        self._closed = True


class _FakePubChannel:
    """AsyncPubChannel replacement --- no-op shell."""

    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs

    @classmethod
    def factory(cls, opts, **kwargs):
        return cls(opts, **kwargs)

    async def connect(self):
        pass

    def on_recv(self, callback):
        pass

    def close(self):
        pass

    async def close_async(self):
        pass


@pytest.fixture
def fake_channels(monkeypatch):
    """Install the fake channel factories on the link module."""
    import salt.channel.client as channel_client
    import salt.topology.link as link_mod

    _FakeReqChannel.sends = []
    _FakeReqChannel.handshake_response = {
        "status": "ok",
        "aes": os.urandom(32),
        "cluster_id": "east",
        "endpoints": [],
    }
    _FakeReqChannel.default_response = {"status": "ok"}
    monkeypatch.setattr(
        channel_client.AsyncReqChannel, "factory", _FakeReqChannel.factory
    )
    monkeypatch.setattr(
        channel_client.AsyncPubChannel, "factory", _FakePubChannel.factory
    )
    monkeypatch.setattr(link_mod, "AsyncReqChannel", _FakeReqChannel, raising=False)
    monkeypatch.setattr(link_mod, "AsyncPubChannel", _FakePubChannel, raising=False)
    yield _FakeReqChannel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reserved_port():
    """Return a free TCP port.  The socket is closed before returning
    so the caller can bind to it.  Short-lived race window is
    acceptable in tests."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return port


@pytest.fixture
def opts(tmp_path):
    """Minimal opts dict with topology enabled."""
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_dir / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_dir),
        "interface": "127.0.0.1",
        "topology_enabled": True,
        "topology_link_port": _reserved_port(),
        "topology_peers": [],
        "topology_registry_cache_size": 512,
        "topology_registry_cache_key_size": 64,
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_detach_quiesce": 0,
        "cluster_id": "self",
    }


@pytest.fixture
def clean_state(monkeypatch):
    """Ensure the module globals are reset before/after each test.

    Uses ``monkeypatch.setattr`` so attribute overrides are reverted
    automatically at fixture teardown.
    """
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    try:
        asyncio.new_event_loop().run_until_complete(link_manager.stop())
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# pre_fork
# ---------------------------------------------------------------------------


def test_pre_fork_materialises_mmap_files(opts, clean_state):
    """``pre_fork`` creates breadcrumb + registry mmap files."""
    link_manager.pre_fork(opts, process_manager=None)
    reg_path = os.path.join(opts["pki_dir"], "master", "topology_registry.mmap")
    br_path = os.path.join(opts["pki_dir"], "master", "topology_breadcrumbs.mmap")
    assert os.path.isfile(reg_path), "registry index not created"
    assert os.path.isfile(br_path), "breadcrumbs index not created"


def test_pre_fork_does_not_reserve_listener_socket(opts, clean_state):
    """
    ``pre_fork`` must NOT bind ``topology_link_port`` in the parent.

    The direct_bind path in
    :class:`salt.transport.zeromq.RequestServer`'s ``post_fork`` binds
    the port inside the publish daemon after fork; a parent-held bound
    fd on the same host:port causes the publish daemon's zmq bind to
    fail with EADDRINUSE.  Also helps Windows CI where ``fcntl`` --
    needed by the old reservation path -- is unavailable.
    """
    link_manager.pre_fork(opts, process_manager=None)
    sock = link_manager._LISTENER_SOCKET  # pylint: disable=protected-access
    assert sock is None, "pre_fork must leave _LISTENER_SOCKET unreserved"


def test_pre_fork_does_not_populate_module_globals(opts, clean_state):
    """``pre_fork`` must NOT touch _LINKS / _INBOUND / _LISTENER / _LISTENER_SOCKET."""
    link_manager.pre_fork(opts, process_manager=None)
    assert link_manager._LINKS == {}  # pylint: disable=protected-access
    assert link_manager._INBOUND == {}  # pylint: disable=protected-access
    assert link_manager._LISTENER is None  # pylint: disable=protected-access
    assert link_manager._LISTENER_SOCKET is None  # pylint: disable=protected-access
    assert link_manager._OWNER_PID is None  # pylint: disable=protected-access


def test_pre_fork_disabled_is_noop(opts, clean_state):
    """``pre_fork`` with ``topology_enabled=False`` returns immediately."""
    opts["topology_enabled"] = False
    link_manager.pre_fork(opts, process_manager=None)
    reg_path = os.path.join(opts["pki_dir"], "master", "topology_registry.mmap")
    assert not os.path.exists(reg_path), "registry should not be created when disabled"


# ---------------------------------------------------------------------------
# start / get_router / idempotency
# ---------------------------------------------------------------------------


def test_start_wires_router(opts, clean_state):
    """``start`` populates :func:`router.get_router`."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        router = router_mod.get_router()
        assert router is not None, "router.get_router() must return the instance"
        assert (
            link_manager._OWNER_PID == os.getpid()
        )  # pylint: disable=protected-access
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_start_idempotent_second_call_warns(opts, clean_state, caplog):
    """Second ``start`` without ``stop`` is a WARNING no-op."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        router_before = router_mod.get_router()
        with caplog.at_level(logging.WARNING, logger="salt.topology.link_manager"):
            loop.run_until_complete(link_manager.start(opts, loop))
        assert router_mod.get_router() is router_before
        assert any(
            "called twice" in rec.message for rec in caplog.records
        ), "expected WARNING about double start"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_start_disabled_short_circuits(opts, clean_state):
    """Disabled topology makes ``start`` return without side effects."""
    opts["topology_enabled"] = False
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        assert router_mod.get_router() is None
        assert link_manager._OWNER_PID is None  # pylint: disable=protected-access
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Owner-PID guard
# ---------------------------------------------------------------------------


def _child_add_link_target(pki_dir_str, link_port, cluster_id, queue):
    """Target used by multiprocessing to assert add_link raises in a
    child process.  The parent's module globals are copied via fork,
    including ``_OWNER_PID``; a child's ``os.getpid()`` differs so
    the guard should fire.
    """
    try:
        child_ref = PeerRef(host="127.0.0.1", port=link_port, finger=None)
        loop = asyncio.new_event_loop()
        link = PeerMasterLink(
            {"cluster_id": "child", "topology_link_port": link_port},
            child_ref,
            loop,
        )
        link._peer_cluster_id = cluster_id  # pylint: disable=protected-access
        link_manager.add_link(link)
    except RuntimeError as exc:
        queue.put(("ok", str(exc)))
        return
    except Exception as exc:  # pylint: disable=broad-except
        queue.put(("other", repr(exc)))
        return
    queue.put(("no-raise", None))


def test_owner_pid_guard_blocks_fork_child(opts, clean_state):
    """``add_link`` from a forked child raises RuntimeError."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        proc = ctx.Process(
            target=_child_add_link_target,
            args=(opts["pki_dir"], opts["topology_link_port"], "east", queue),
        )
        proc.start()
        proc.join(timeout=30)
        status, detail = queue.get(timeout=5)
        assert status == "ok", f"expected RuntimeError in child; got {status}:{detail}"
        assert "PID" in detail, f"expected PID in guard message; got {detail!r}"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


# ---------------------------------------------------------------------------
# _handle_master_auth
# ---------------------------------------------------------------------------


def test_handle_master_auth_unseen_writes_pending_and_retries(opts, clean_state):
    """First contact writes to ``masters_pre/`` and replies retry."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        peer_pub = b"-----BEGIN FAKE PEER PUB-----\n"
        load = {
            "cmd": "_master_auth",
            "cluster_id": "east",
            "public_key": peer_pub,
        }
        reply = loop.run_until_complete(
            link_manager._handle_master_auth(load)
        )  # pylint: disable=protected-access
        assert reply["status"] == "retry"
        pending = os.path.join(opts["pki_dir"], "masters_pre", "east.pub")
        assert os.path.isfile(pending), "pending key file not written"
        with salt.utils.files.fopen(pending, "rb") as fh:
            assert fh.read() == peer_pub
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_master_auth_accepted_returns_ok(opts, clean_state):
    """A peer whose key is in ``masters/`` gets ``ok`` + session AES."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        # Simulate operator having run salt-key -a east --master.
        accepted = os.path.join(opts["pki_dir"], "masters", "east.pub")
        with salt.utils.files.fopen(accepted, "wb") as fh:
            fh.write(b"-----BEGIN ACCEPTED PEER PUB-----\n")
        reply = loop.run_until_complete(
            link_manager._handle_master_auth(
                {"cmd": "_master_auth", "cluster_id": "east"}
            )  # pylint: disable=protected-access
        )
        assert reply["status"] == "ok"
        assert isinstance(reply["aes"], (bytes, bytearray)) and len(reply["aes"]) == 32
        assert reply["endpoints"], "accepted reply must advertise local endpoints"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_master_auth_rejects_rejected_peer(opts, clean_state):
    """A peer in ``masters_rejected/`` or ``masters_denied/`` gets rejected."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        rejected = os.path.join(opts["pki_dir"], "masters_rejected", "east.pub")
        with salt.utils.files.fopen(rejected, "wb") as fh:
            fh.write(b"-----BEGIN REJECTED-----\n")
        reply = loop.run_until_complete(
            link_manager._handle_master_auth(
                {"cmd": "_master_auth", "cluster_id": "east"}
            )  # pylint: disable=protected-access
        )
        assert reply["status"] == "rejected"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_master_auth_rejects_reserved_cluster_id(opts, clean_state):
    """Reserved MmapCache sentinel names are rejected."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        for bad in ("__identity_pub__", "__identity_version__"):
            reply = loop.run_until_complete(
                link_manager._handle_master_auth(
                    {"cmd": "_master_auth", "cluster_id": bad}
                )  # pylint: disable=protected-access
            )
            assert reply["status"] == "rejected", f"expected reject on {bad!r}"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


# ---------------------------------------------------------------------------
# _handle_inbound dispatch
# ---------------------------------------------------------------------------


class _FakeRouter:
    """Captures router dispatch calls for test assertions."""

    def __init__(self):
        self.forward_publish_calls = []
        self.route_return_calls = []
        self.route_event_calls = []
        self.ingest_summary_calls = []

    def forward_publish(self, load, inbound_link):
        self.forward_publish_calls.append((load, inbound_link))
        return "forward-ok"

    def route_return(self, ret):
        self.route_return_calls.append(ret)
        return "return-ok"

    def route_event(self, event):
        self.route_event_calls.append(event)
        return "event-ok"

    def ingest_summary(self, summary, inbound_link):
        self.ingest_summary_calls.append((summary, inbound_link))
        return "summary-ok"


def _install_fake_inbound_link(cluster_id, session_generation=1):
    """Pre-populate _INBOUND with a stub link so session verification passes."""

    class _Stub:
        pass

    stub = _Stub()
    stub.peer_cluster_id = cluster_id
    stub.session_generation = session_generation
    stub.health = LinkHealth.CONNECTED
    link_manager._INBOUND[cluster_id] = stub  # pylint: disable=protected-access
    return stub


def test_handle_inbound_dispatches_pub(opts, clean_state, monkeypatch):
    """``topology/pub`` dispatches to router.forward_publish."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouter()
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        _install_fake_inbound_link("east", session_generation=7)
        payload = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 7,
            "load": {"jid": "20260101000000000000"},
        }
        result = loop.run_until_complete(
            link_manager._handle_inbound(payload)
        )  # pylint: disable=protected-access
        assert result == "forward-ok"
        assert len(fake.forward_publish_calls) == 1
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_inbound_dispatches_ret_evt_sum(opts, clean_state, monkeypatch):
    """``topology/ret``, ``topology/evt``, ``topology/sum`` fan out correctly."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouter()
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        _install_fake_inbound_link("east", session_generation=3)
        # ``_dispatch_ret`` iterates a ``batch`` of per-minion returns and
        # calls ``route_return(item)`` for each item with a ``jid`` (items
        # without a jid are dropped before the router sees them).  Craft
        # a minimal valid batch so the dispatch exercises ``route_return``.
        # ``_dispatch_evt`` / ``_dispatch_sum`` still take an opaque load.
        payloads = {
            "topology/ret": {"batch": [{"jid": "20260101000000000001", "id": "m"}]},
            "topology/evt": {"blob": "topology/evt"},
            "topology/sum": {"blob": "topology/sum"},
        }
        for tag, bucket in (
            ("topology/ret", fake.route_return_calls),
            ("topology/evt", fake.route_event_calls),
            ("topology/sum", fake.ingest_summary_calls),
        ):
            payload = {
                "tag": tag,
                "origin_cluster_id": "east",
                "session_generation": 3,
                "load": payloads[tag],
            }
            loop.run_until_complete(
                link_manager._handle_inbound(payload)
            )  # pylint: disable=protected-access
            assert bucket, f"{tag} did not dispatch"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_inbound_bad_session_dropped(opts, clean_state, caplog, monkeypatch):
    """A payload with a stale session generation is dropped at WARNING."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouter()
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        _install_fake_inbound_link("east", session_generation=5)
        payload = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 1,  # stale
            "load": {},
        }
        with caplog.at_level(logging.WARNING, logger="salt.topology.link_manager"):
            result = loop.run_until_complete(
                link_manager._handle_inbound(payload)
            )  # pylint: disable=protected-access
        assert result is None
        assert (
            not fake.forward_publish_calls
        ), "stale-session payload should NOT dispatch"
        assert any(
            "bad/missing session" in rec.message for rec in caplog.records
        ), "expected WARNING on bad session"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_inbound_unknown_tag_dropped(opts, clean_state, monkeypatch):
    """Unknown tags are dropped silently (DEBUG, not WARNING)."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouter()
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        payload = {"tag": "topology/nonsense"}
        result = loop.run_until_complete(
            link_manager._handle_inbound(payload)
        )  # pylint: disable=protected-access
        assert result is None
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


class _FakeRouterWithLocalMatch:
    """
    Router stub that returns ``(links, local_match)`` from
    ``forward_publish`` so :func:`_dispatch_pub` can exercise the
    local-publish branch.
    """

    def __init__(self, local_match=True):
        self._local_match = local_match
        self.calls = []

    def forward_publish(self, load, inbound_link):
        self.calls.append((load, inbound_link))
        return [], self._local_match


def test_handle_inbound_pub_local_match_publishes_to_local_minions(
    opts, clean_state, monkeypatch
):
    """
    When ``forward_publish`` returns ``local_match=True`` on an
    inbound ``topology/pub``, the dispatcher must call
    :func:`_publish_to_local_minions` so west dispatches the
    forwarded publish to its own minions.  Pre-fix the local-match
    flag was computed but never acted on.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouterWithLocalMatch(local_match=True)
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        _install_fake_inbound_link("east", session_generation=11)

        local_calls = []

        async def _spy_publish(load):
            local_calls.append(load)

        monkeypatch.setattr(link_manager, "_publish_to_local_minions", _spy_publish)
        payload = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 11,
            "load": {
                "jid": "20260101000000000000",
                "tgt": "C@west and *",
                "tgt_type": "compound",
                "fun": "test.ping",
            },
        }
        result = loop.run_until_complete(
            link_manager._handle_inbound(payload)
        )  # pylint: disable=protected-access
        assert result == ([], True)
        assert len(local_calls) == 1, (
            f"local-minion publish not dispatched for local_match=True: "
            f"calls={local_calls!r}"
        )
        assert local_calls[0]["jid"] == "20260101000000000000"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_handle_inbound_pub_no_local_match_skips_local_publish(
    opts, clean_state, monkeypatch
):
    """
    Transit-only case: when ``forward_publish`` returns
    ``local_match=False`` (this cluster is in the path but is not a
    named destination), the dispatcher must NOT publish to local
    minions.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        fake = _FakeRouterWithLocalMatch(local_match=False)
        monkeypatch.setattr(router_mod, "_ROUTER", fake)
        _install_fake_inbound_link("east", session_generation=13)

        local_calls = []

        async def _spy_publish(load):
            local_calls.append(load)

        monkeypatch.setattr(link_manager, "_publish_to_local_minions", _spy_publish)
        payload = {
            "tag": "topology/pub",
            "origin_cluster_id": "east",
            "session_generation": 13,
            "load": {
                "jid": "20260101000000000001",
                "tgt": "C@north and *",
                "tgt_type": "compound",
            },
        }
        result = loop.run_until_complete(
            link_manager._handle_inbound(payload)
        )  # pylint: disable=protected-access
        assert result == ([], False)
        assert (
            local_calls == []
        ), f"local-minion publish fired on transit-only hop: {local_calls!r}"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_publish_to_local_minions_strips_c_scope(opts, clean_state, monkeypatch):
    """
    :func:`_publish_to_local_minions` must call
    :func:`salt.topology.router.strip_cluster_scope` on the target
    before handing off to the PubServerChannel so the minion-side
    compound matcher never sees the ``C@`` clause.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))

        published = []

        class _FakePubChannel:
            def __init__(self, opts):
                self.opts = opts

            @classmethod
            def factory(cls, opts, **kwargs):
                return cls(opts)

            async def publish(self, load):
                published.append(load)

        import salt.channel.server as server_mod

        monkeypatch.setattr(
            server_mod, "PubServerChannel", _FakePubChannel, raising=True
        )
        # Force a single transport pass regardless of system defaults.
        monkeypatch.setattr(
            "salt.utils.channel.iter_transport_opts",
            lambda _opts: [("zeromq", opts)],
        )
        load = {
            "jid": "20260101000000000002",
            "tgt": "C@west and web-*",
            "tgt_type": "compound",
            "fun": "test.ping",
        }
        loop.run_until_complete(
            link_manager._publish_to_local_minions(load)
        )  # pylint: disable=protected-access
        assert len(published) == 1, published
        # ``C@west`` must have been stripped; "web-*" remains.
        assert "C@" not in str(
            published[0]["tgt"]
        ), f"stripped target still contains C@: {published[0]!r}"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


def test_stop_clears_module_state(opts, clean_state):
    """``stop`` resets globals and get_router returns None."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        assert router_mod.get_router() is not None
        loop.run_until_complete(link_manager.stop())
        assert router_mod.get_router() is None
        assert link_manager._OWNER_PID is None  # pylint: disable=protected-access
        assert link_manager._LINKS == {}  # pylint: disable=protected-access
        assert link_manager._INBOUND == {}  # pylint: disable=protected-access
    finally:
        loop.close()


def test_stop_is_idempotent(opts, clean_state):
    """A second ``stop`` is a no-op."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        loop.run_until_complete(link_manager.stop())
        # Second stop must not raise.
        loop.run_until_complete(link_manager.stop())
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# End-to-end: two_cluster_fixture handshake
# ---------------------------------------------------------------------------


def test_two_master_handshake_e2e(two_cluster_fixture, clean_state):
    """Two running masters: west.accept_peer(east), then east drives
    ``_handle_master_auth`` directly against west's pki_dir to confirm
    the handshake completes with status=ok.

    The topology code is not yet wired into the master-startup path,
    so this test drives :func:`link_manager._handle_master_auth`
    inside this process pointed at the harness's pki_dir ---
    sufficient to verify the key-file protocol end-to-end.
    """
    east, west = two_cluster_fixture
    # west accepts east's identity.
    west.accept_peer(east)

    # Build opts pointing at west's pki_dir so handle_master_auth
    # sees the accepted file west just wrote.  Cache-size opts MUST
    # mirror the running master's config so the writer we open here
    # matches the MmapCache files the salt-master's own ``pre_fork``
    # already materialised.  A size mismatch between pre-created
    # files and the writer makes ``open_writer`` raise
    # ``RuntimeError("failed to open topology breadcrumbs writer at
    # ... (did pre_create run?)")`` --- the test harness equivalent
    # of the production bug fixed in
    # ``MasterPubServerChannel.pre_fork``.
    west_opts = west.master_opts(peer_index=0)
    west_opts["cluster_id"] = "west"
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(west_opts, loop))
        reply = loop.run_until_complete(
            link_manager._handle_master_auth(
                {"cmd": "_master_auth", "cluster_id": "east"}
            )  # pylint: disable=protected-access
        )
        assert reply["status"] == "ok", f"handshake did not accept east: {reply!r}"
        assert reply["cluster_id"] == "west"
        assert reply["endpoints"], "accept must advertise own endpoints"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()
