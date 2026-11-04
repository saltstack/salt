"""
Unit tests for :mod:`salt.topology.link_manager`.

Focuses on invariants that do NOT require a running master or
subprocess fork: dispatch table shape, owner-PID guard behaviour
under child-PID emulation, ``start`` step ordering, and the
``_LINKS``/``_INBOUND`` dedup logic in ``get_all_links`` /
``outbound_links``.
"""

import asyncio
import os
import socket

import pytest

import salt.topology.link_manager as link_manager
import salt.topology.router as router_mod
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reserved_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def opts(tmp_path):
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
        "cluster_id": "self",
    }


@pytest.fixture
def clean_state(monkeypatch):
    link_manager._reset_module_state()  # pylint: disable=protected-access
    monkeypatch.setattr(router_mod, "_ROUTER", None)
    yield
    try:
        asyncio.new_event_loop().run_until_complete(link_manager.stop())
    except Exception:  # pylint: disable=broad-except
        pass
    link_manager._reset_module_state()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


def test_dispatch_table_contains_required_tags():
    """``_DISPATCH_TABLE`` has an entry for every tag named in the RFC."""
    table = link_manager._DISPATCH_TABLE  # pylint: disable=protected-access
    required = {
        "_master_auth",
        "topology/_master_auth",
        "topology/pub",
        "topology/ret",
        "topology/evt",
        "topology/sum",
    }
    assert required <= set(table), f"missing dispatch entries: {required - set(table)}"


def test_dispatch_table_values_are_callables():
    """Every dispatch entry resolves to a plain callable."""
    for (
        tag,
        fn,
    ) in link_manager._DISPATCH_TABLE.items():  # pylint: disable=protected-access
        assert callable(fn), f"dispatch for {tag!r} not callable: {fn!r}"


# ---------------------------------------------------------------------------
# Owner-PID guard
# ---------------------------------------------------------------------------


def test_owner_pid_guard_raises_on_mismatch(opts, clean_state, monkeypatch):
    """Emulate a child PID without forking by patching :func:`os.getpid`.
    The guard must raise RuntimeError when the caller's PID differs
    from the recorded owner.
    """
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        # Pretend we're a different process.
        monkeypatch.setattr(
            os, "getpid", lambda: link_manager._OWNER_PID + 1
        )  # pylint: disable=protected-access
        with pytest.raises(RuntimeError, match="PID"):
            # Use a dummy link; add_link's TypeError check should not
            # fire because the PID guard runs first.
            link_manager.add_link(object())
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_owner_pid_guard_before_start_is_noop(clean_state):
    """When ``_OWNER_PID`` is still None (no start), the guard is a no-op."""
    # Should not raise.
    link_manager._check_owner_pid()  # pylint: disable=protected-access


# ---------------------------------------------------------------------------
# start step ordering
# ---------------------------------------------------------------------------


def test_start_opens_mmaps_before_router_construction(opts, clean_state, monkeypatch):
    """The ``TopologyRouter(...)`` constructor receives already-opened
    cache handles --- the registry open must happen BEFORE the router
    is built.
    """
    seen = {}

    import salt.topology.breadcrumbs as br
    import salt.topology.registry as reg

    real_open_writer_reg = reg.open_writer
    real_open_writer_br = br.open_writer
    real_router_cls = router_mod.TopologyRouter

    def _wrapped_reg_open(opts_in):
        seen["registry_opened"] = True
        return real_open_writer_reg(opts_in)

    def _wrapped_br_open(opts_in):
        seen["breadcrumbs_opened"] = True
        return real_open_writer_br(opts_in)

    class _WrappedRouter(real_router_cls):
        def __init__(self, opts_in, reg_cache, br_cache):
            seen["router_built"] = True
            seen["registry_before_router"] = seen.get("registry_opened", False)
            seen["breadcrumbs_before_router"] = seen.get("breadcrumbs_opened", False)
            try:
                super().__init__(opts_in, reg_cache, br_cache)
            except TypeError:
                pass

    monkeypatch.setattr(reg, "open_writer", _wrapped_reg_open)
    monkeypatch.setattr(br, "open_writer", _wrapped_br_open)
    monkeypatch.setattr(router_mod, "TopologyRouter", _WrappedRouter)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        assert seen.get("router_built"), "router was never constructed"
        assert seen.get(
            "registry_before_router"
        ), "registry MmapCache must be opened BEFORE TopologyRouter"
        assert seen.get(
            "breadcrumbs_before_router"
        ), "breadcrumbs MmapCache must be opened BEFORE TopologyRouter"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


def test_start_registers_sm_callbacks_before_migration(opts, clean_state, monkeypatch):
    """When a Raft service is provided, SM wrapping happens BEFORE the
    migration step runs --- otherwise entries proposed during
    migration would commit without firing the publish-daemon's
    add_link path.
    """
    order = []

    class _FakeSM:
        def __init__(self):
            from salt.cluster.consensus.raft.log import LogEntryType

            self._handlers = {
                LogEntryType.MASTER_PEER_ATTACH: lambda e: None,
                LogEntryType.MASTER_PEER_DETACH: lambda e: None,
            }

        def _handle_peer_attach(self, entry):
            pass

        def _handle_peer_detach(self, entry):
            pass

    class _FakeRaftService:
        def __init__(self):
            self.topology_sm = _FakeSM()

    svc = _FakeRaftService()

    import salt.topology.migration as migration

    original_install = (
        link_manager._install_sm_callbacks
    )  # pylint: disable=protected-access
    original_needs = migration.needs_migration

    def _wrapped_install(sm):
        order.append("install_cb")
        return original_install(sm)

    def _wrapped_needs(opts_in):
        order.append("needs_migration")
        return False

    monkeypatch.setattr(link_manager, "_install_sm_callbacks", _wrapped_install)
    monkeypatch.setattr(migration, "needs_migration", _wrapped_needs)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop, raft_service=svc))
        assert order.index("install_cb") < order.index(
            "needs_migration"
        ), f"SM callbacks must install before migration check; got {order}"
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


# ---------------------------------------------------------------------------
# _LINKS / _INBOUND dedup
# ---------------------------------------------------------------------------


class _StubLink:
    """Minimal link stand-in for dedup tests."""

    def __init__(self, cluster_id, health=LinkHealth.CONNECTED):
        self.peer_cluster_id = cluster_id
        self.health = health
        self.session_generation = 1
        self.endpoints = (PeerRef(host="127.0.0.1", port=1234, finger=None),)

    async def disconnect(self):
        pass

    async def quiesce(self):
        pass


def test_get_all_links_dedup_by_cluster_id(clean_state):
    """When both inbound and outbound links exist for one peer,
    ``get_all_links`` returns one entry.
    """
    outbound = _StubLink("east")
    inbound = _StubLink("east")
    link_manager._LINKS["east"] = outbound  # pylint: disable=protected-access
    link_manager._INBOUND["east"] = inbound  # pylint: disable=protected-access
    links = link_manager.get_all_links()
    assert len(links) == 1, f"expected 1 deduped link; got {len(links)}"
    # Outbound wins when both are CONNECTED (we initiated it).
    assert links[0] is outbound


def test_get_all_links_filters_pending_provisional_keys(clean_state):
    """Provisional ``__pending__:...`` keys do not surface in get_all_links."""
    out = _StubLink("east")
    pending = _StubLink(None)
    link_manager._LINKS["east"] = out  # pylint: disable=protected-access
    link_manager._LINKS["__pending__:1.2.3.4:9000"] = (
        pending  # pylint: disable=protected-access
    )
    links = link_manager.get_all_links()
    assert links == [out]


def test_outbound_links_excludes_inbound_and_pending(clean_state):
    """``outbound_links`` returns only the outbound set, minus
    provisional entries.
    """
    out = _StubLink("east")
    pending = _StubLink(None)
    in_only = _StubLink("west")
    link_manager._LINKS["east"] = out  # pylint: disable=protected-access
    link_manager._LINKS["__pending__:9.9.9.9:1"] = (
        pending  # pylint: disable=protected-access
    )
    link_manager._INBOUND["west"] = in_only  # pylint: disable=protected-access
    assert link_manager.outbound_links() == [out]


def test_get_link_prefers_connected_half(clean_state):
    """When both halves exist and only one is CONNECTED, ``get_link``
    returns the connected one."""
    out = _StubLink("east", health=LinkHealth.DISCONNECTED)
    inb = _StubLink("east", health=LinkHealth.CONNECTED)
    link_manager._LINKS["east"] = out  # pylint: disable=protected-access
    link_manager._INBOUND["east"] = inb  # pylint: disable=protected-access
    assert link_manager.get_link("east") is inb


def test_get_link_returns_none_for_unknown(clean_state):
    """A cluster id with no registered link returns None, not raises."""
    assert link_manager.get_link("nonexistent") is None


def test_remove_link_is_idempotent(opts, clean_state):
    """``remove_link`` on an unknown cluster_id is a no-op (no raise)."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(link_manager.start(opts, loop))
        # No link registered.  Must not raise.
        link_manager.remove_link("ghost")
    finally:
        loop.run_until_complete(link_manager.stop())
        loop.close()


# ---------------------------------------------------------------------------
# ``_INBOUND`` lock discipline (regression)
# ---------------------------------------------------------------------------
#
# ``_INBOUND`` is mutated from two different thread contexts: the publish
# daemon's asyncio loop (``_handle_master_auth`` + ``_maybe_lazy_register_
# inbound``) and the Raft-SM apply thread (``remove_link``).  The latter
# pops ``_INBOUND[cluster_id]`` under ``_LOCK``; the former two must take
# the same lock across their writes to prevent a detach landing
# mid-registration from leaving a stale record resurrected.
#
# These tests use an instrumented ``_INBOUND`` dict that records every
# ``__setitem__`` call made while ``_LOCK`` is NOT owned by the current
# thread; a nonzero count indicates one of the write paths dropped the
# lock discipline (or a new write path was added without it).


class _LockWitnessDict(dict):
    """A ``dict`` subclass that counts ``__setitem__`` calls made without
    ``_lock`` held by the current thread.

    Uses :meth:`threading.RLock._is_owned`, which is a CPython
    implementation detail that has been stable across versions and is the
    only API that lets us assert "lock X is currently held by this
    thread" without actually trying to acquire.
    """

    def __init__(self, lock):
        super().__init__()
        self._lock = lock
        self.unlocked_writes = 0

    def __setitem__(self, key, value):
        if not self._lock._is_owned():  # pylint: disable=protected-access
            self.unlocked_writes += 1
        super().__setitem__(key, value)


@pytest.fixture
def inbound_lock_witness(monkeypatch):
    """Replace ``_INBOUND`` with a :class:`_LockWitnessDict` and yield it.

    Reset at teardown via the standard ``clean_state`` fixture semantics.
    """
    witness = _LockWitnessDict(link_manager._LOCK)  # pylint: disable=protected-access
    monkeypatch.setattr(link_manager, "_INBOUND", witness)
    return witness


def test_handle_master_auth_holds_lock_on_inbound_write(
    opts, clean_state, inbound_lock_witness, monkeypatch
):
    """Regression: ``_handle_master_auth`` must hold ``_LOCK`` across
    its ``_INBOUND[cluster_id]`` write.  Without the lock, a concurrent
    ``remove_link`` on the Raft-SM apply thread can leave a stale
    inbound record for a cluster_id the SM has just detached.
    """
    # ``_handle_master_auth`` consults ``_current_opts(load)`` which
    # reads module-level ``_OPTS``; populate it directly.
    monkeypatch.setattr(link_manager, "_OPTS", opts)

    # Pre-create the accepted-key sentinel so the auth path reaches the
    # ``_INBOUND`` registration branch.
    accepted = (
        pytest.importorskip("pathlib").Path(opts["pki_dir"]) / "masters" / "east.pub"
    )
    accepted.parent.mkdir(parents=True, exist_ok=True)
    accepted.write_bytes(
        b"-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----\n"
    )

    load = {"cluster_id": "east", "nonce": "deadbeef"}
    reply = asyncio.new_event_loop().run_until_complete(
        link_manager._handle_master_auth(load)  # pylint: disable=protected-access
    )

    assert reply["status"] == "ok"
    assert "east" in inbound_lock_witness, "handshake did not populate _INBOUND"
    assert inbound_lock_witness.unlocked_writes == 0, (
        f"_handle_master_auth wrote _INBOUND without _LOCK held "
        f"({inbound_lock_witness.unlocked_writes} unlocked writes)"
    )


def test_handle_master_auth_pins_generation_across_cluster_node_reauth(
    opts, clean_state, monkeypatch
):
    """Regression: in a 3-master peer cluster each node auths
    independently against ``_handle_master_auth``.  If the handler
    incremented ``session_generation`` on every call the 3-node
    sender would end up at gen=3 while nodes that got gen=1 and
    gen=2 still have stale state --- every frame from them fails
    :func:`_verify_session`.

    Fix: only bump when creating a fresh entry.  Re-auth calls
    reuse the existing gen so all N cluster-nodes converge.  The
    reply must also carry ``session_generation`` so the sender
    can pin its own counter.
    """
    monkeypatch.setattr(link_manager, "_OPTS", opts)
    accepted = (
        pytest.importorskip("pathlib").Path(opts["pki_dir"]) / "masters" / "east.pub"
    )
    accepted.parent.mkdir(parents=True, exist_ok=True)
    accepted.write_bytes(
        b"-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----\n"
    )

    load = {"cluster_id": "east", "nonce": "deadbeef"}
    loop = asyncio.new_event_loop()
    try:
        first = loop.run_until_complete(
            link_manager._handle_master_auth(load)  # pylint: disable=protected-access
        )
        second = loop.run_until_complete(
            link_manager._handle_master_auth(load)  # pylint: disable=protected-access
        )
        third = loop.run_until_complete(
            link_manager._handle_master_auth(load)  # pylint: disable=protected-access
        )
    finally:
        loop.close()

    # Each reply must carry the server-side gen so the sender pins.
    assert first.get("session_generation") == 1
    # Re-auth from nodes 2 and 3 of the same cluster must reuse the
    # existing gen, not increment.  This is the regression guard.
    assert second.get("session_generation") == 1
    assert third.get("session_generation") == 1
    # And the module-level _INBOUND must agree.
    assert (
        link_manager._INBOUND["east"].session_generation == 1
    )  # pylint: disable=protected-access


def test_maybe_lazy_register_inbound_holds_lock_on_inbound_write(
    opts, clean_state, inbound_lock_witness, monkeypatch
):
    """Regression: ``_maybe_lazy_register_inbound`` must hold ``_LOCK``
    across its ``_INBOUND[origin]`` write.  Same race window as
    :func:`_handle_master_auth` --- a Raft-SM detach landing between
    the staleness check and the write would resurrect a stale record.
    """
    monkeypatch.setattr(link_manager, "_OPTS", opts)
    accepted = (
        pytest.importorskip("pathlib").Path(opts["pki_dir"]) / "masters" / "east.pub"
    )
    accepted.parent.mkdir(parents=True, exist_ok=True)
    accepted.write_bytes(
        b"-----BEGIN PUBLIC KEY-----\nstub\n-----END PUBLIC KEY-----\n"
    )

    payload = {
        "tag": "topology/pub",
        "origin_cluster_id": "east",
        "session_generation": 1,
    }
    link_manager._maybe_lazy_register_inbound(
        payload
    )  # pylint: disable=protected-access

    assert "east" in inbound_lock_witness, "lazy-register did not populate _INBOUND"
    assert inbound_lock_witness.unlocked_writes == 0, (
        f"_maybe_lazy_register_inbound wrote _INBOUND without _LOCK held "
        f"({inbound_lock_witness.unlocked_writes} unlocked writes)"
    )


# ---------------------------------------------------------------------------
# _dispatch_sum --- summary ingest wire-form reconstitution + offload
# ---------------------------------------------------------------------------


def test_dispatch_sum_deserializes_summary_before_ingest(monkeypatch):
    """BUG-001/002/006 regression: ``_dispatch_sum`` must reconstitute
    the wire-form summary via :func:`summary_mod.deserialize` before
    passing to :meth:`TopologyRouter.ingest_summary`.  Prior to the
    fix, the raw dict was handed in and ``ingest_summary`` tripped
    ``AttributeError: 'dict' object has no attribute 'path'`` on
    every inbound ``topology/sum`` -- flooding stayed the fallback and
    ``topology.links()`` reported every peer as ``disconnected``."""
    import salt.topology.link_manager as lm
    import salt.topology.summary as summary_mod

    sentinel_summary = object()
    captured = {}

    def _fake_deserialize(wire):
        captured["wire"] = wire
        return sentinel_summary

    class _FakeRouter:
        async def ingest_summary(self, summary, inbound_link):
            captured["summary"] = summary
            captured["inbound_link"] = inbound_link

    class _FakeLoop:
        def __init__(self):
            self.scheduled = []

        def is_running(self):
            return True

    fake_loop = _FakeLoop()

    scheduled = []

    def _fake_ensure_future(coro):
        scheduled.append(coro)
        # Drain so the coroutine actually runs and `captured` populates.
        asyncio.new_event_loop().run_until_complete(coro)
        return None

    monkeypatch.setattr(summary_mod, "deserialize", _fake_deserialize)
    monkeypatch.setattr(lm.router_mod, "get_router", _FakeRouter)
    monkeypatch.setattr(lm.asyncio, "ensure_future", _fake_ensure_future)

    wire_dict = {"cluster_id": "west", "path": ["west"]}
    payload = {
        "load": {"summary": wire_dict},
        "origin_cluster_id": "west",
    }

    lm._dispatch_sum(payload)  # pylint: disable=protected-access

    assert captured["wire"] is wire_dict, "deserialize not called with wire body"
    assert (
        captured["summary"] is sentinel_summary
    ), "ingest_summary did not receive the deserialized summary"
    assert scheduled, "ingest_summary was not scheduled via asyncio.ensure_future"


def test_dispatch_sum_drops_missing_summary_body(monkeypatch, caplog):
    """A ``topology/sum`` payload without a ``summary`` key must be
    dropped (debug-logged) without raising and without scheduling
    anything on the loop."""
    import logging

    import salt.topology.link_manager as lm

    class _FakeRouter:
        async def ingest_summary(self, summary, inbound_link):  # pragma: no cover
            raise AssertionError("ingest_summary must not be called")

    scheduled = []
    monkeypatch.setattr(lm.router_mod, "get_router", _FakeRouter)
    monkeypatch.setattr(lm.asyncio, "ensure_future", scheduled.append)

    with caplog.at_level(logging.DEBUG, logger="salt.topology.link_manager"):
        lm._dispatch_sum(  # pylint: disable=protected-access
            {"load": {}, "origin_cluster_id": "west"}
        )

    assert scheduled == []
    assert any(
        "dropping topology/sum with no summary body" in rec.getMessage()
        for rec in caplog.records
    )


def test_dispatch_sum_swallows_deserialize_errors(monkeypatch, caplog):
    """A ``summary_mod.deserialize`` exception must be logged and
    swallowed; the dispatcher returns ``None`` and schedules nothing."""
    import logging

    import salt.topology.link_manager as lm
    import salt.topology.summary as summary_mod

    def _boom(_):
        raise ValueError("corrupt wire")

    class _FakeRouter:
        async def ingest_summary(self, summary, inbound_link):  # pragma: no cover
            raise AssertionError("ingest_summary must not be called")

    scheduled = []
    monkeypatch.setattr(summary_mod, "deserialize", _boom)
    monkeypatch.setattr(lm.router_mod, "get_router", _FakeRouter)
    monkeypatch.setattr(lm.asyncio, "ensure_future", scheduled.append)

    with caplog.at_level(logging.ERROR, logger="salt.topology.link_manager"):
        lm._dispatch_sum(  # pylint: disable=protected-access
            {"load": {"summary": {"anything": "goes"}}, "origin_cluster_id": "west"}
        )

    assert scheduled == []
    assert any(
        "topology/sum deserialize failed" in rec.getMessage() for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# Reconnect sweep --- BUG-016 regression
# ---------------------------------------------------------------------------


class _ReconnectWitnessLink:
    """A link-shape stub that records whether ``connect`` was scheduled."""

    def __init__(self, cluster_id, health):
        self.peer_cluster_id = cluster_id
        self.health = health
        self.session_generation = 1
        self.endpoints = (PeerRef(host="127.0.0.1", port=4515, finger=None),)
        self.send_fault_count = 1 if health == LinkHealth.DEGRADED else 0
        self.connects = 0

    async def connect(self):
        self.connects += 1
        self.health = LinkHealth.CONNECTED

    async def send_summary(self, _summary):
        pass


def test_reconnect_loop_schedules_degraded_links(clean_state, monkeypatch):
    """BUG-016: the periodic sweep MUST schedule ``_connect_and_register``
    for every outbound link in DEGRADED or DISCONNECTED health, and MUST
    NOT touch CONNECTED or provisional-key links.

    Guards the recovery path for the regression scenario on BUG-016:
    a send fault tears down the REQ channel and marks the link
    DEGRADED; without this sweep the link would stay wedged until
    master restart.
    """
    degraded = _ReconnectWitnessLink("east", LinkHealth.DEGRADED)
    disconnected = _ReconnectWitnessLink("south", LinkHealth.DISCONNECTED)
    healthy = _ReconnectWitnessLink("west", LinkHealth.CONNECTED)
    pending = _ReconnectWitnessLink(None, LinkHealth.CONNECTING)

    link_manager._LINKS.clear()  # pylint: disable=protected-access
    link_manager._LINKS["east"] = degraded  # pylint: disable=protected-access
    link_manager._LINKS["south"] = disconnected  # pylint: disable=protected-access
    link_manager._LINKS["west"] = healthy  # pylint: disable=protected-access
    link_manager._LINKS["__pending__:1.2.3.4:9000"] = (
        pending  # pylint: disable=protected-access
    )

    # Shrink the sweep cadence so the test does not wait seconds.
    monkeypatch.setattr(link_manager, "_RECONNECT_INTERVAL", 0.01)

    scheduled = []
    real_ensure_future = asyncio.ensure_future

    def _fake_ensure_future(coro, *args, **kwargs):
        # Capture only the ``_connect_and_register`` scheduling calls
        # the reconnect loop issues; let every OTHER ``ensure_future``
        # call (including the test's own scheduling of ``_reconnect_loop``)
        # fall through to the real implementation.
        name = getattr(coro, "__name__", None) or getattr(
            getattr(coro, "cr_code", None), "co_name", ""
        )
        if name == "_connect_and_register":
            scheduled.append(coro)
            coro.close()

            class _Dummy:
                def cancel(self):
                    pass

            return _Dummy()
        return real_ensure_future(coro, *args, **kwargs)

    monkeypatch.setattr(link_manager.asyncio, "ensure_future", _fake_ensure_future)

    async def _run():
        task = asyncio.ensure_future(link_manager._reconnect_loop({}))
        # Give the sweep one tick.
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.new_event_loop().run_until_complete(_run())

    # Exactly two scheduled reconnects: one for ``east`` (DEGRADED),
    # one for ``south`` (DISCONNECTED).  The CONNECTED and provisional-
    # key-mid-CONNECTING entries must not be touched.
    assert len(scheduled) >= 2, f"expected >=2 reconnects; got {len(scheduled)}"
    # Idempotence over multiple ticks: at least one reconnect per
    # degraded/disconnected link.  (The healthy / pending stayed off.)
    assert healthy.connects == 0
    assert pending.connects == 0


def test_reconnect_loop_recovers_provisional_disconnected_links(
    clean_state, monkeypatch
):
    """BUG-022: a link whose FIRST handshake left it in
    :data:`LinkHealth.DISCONNECTED` or
    :data:`LinkHealth.PENDING_ACCEPT` under a provisional
    ``__pending__:host:port`` key MUST be re-scheduled by the
    reconnect sweeper.

    Pre-fix: the sweeper short-circuited on ``__pending__:`` prefix
    believing a connect task was still in flight.  In the clustered-
    master sandbox the receiver's ``_cluster_is_ready`` gate returned
    ``cluster_retry`` for every handshake attempt until the receiver's
    Raft committed; the sender's first-pass bounded retry burned out,
    marked the link DISCONNECTED/PENDING_ACCEPT under its provisional
    key, and the sweeper then ignored it -- 22/24 masters stayed stuck
    on ``configured`` forever.

    Post-fix: the sweeper SKIPs provisional keys only while they are
    actively CONNECTING; the terminal states fall through and get a
    fresh ``_connect_and_register`` scheduled.
    """
    disconnected_pending = _ReconnectWitnessLink(None, LinkHealth.DISCONNECTED)
    pending_accept_pending = _ReconnectWitnessLink(None, LinkHealth.PENDING_ACCEPT)
    connecting_pending = _ReconnectWitnessLink(None, LinkHealth.CONNECTING)

    link_manager._LINKS.clear()  # pylint: disable=protected-access
    link_manager._LINKS["__pending__:1.1.1.1:4515"] = (
        disconnected_pending  # pylint: disable=protected-access
    )
    link_manager._LINKS["__pending__:2.2.2.2:4515"] = (
        pending_accept_pending  # pylint: disable=protected-access
    )
    link_manager._LINKS["__pending__:3.3.3.3:4515"] = (
        connecting_pending  # pylint: disable=protected-access
    )

    monkeypatch.setattr(link_manager, "_RECONNECT_INTERVAL", 0.01)

    scheduled = []
    real_ensure_future = asyncio.ensure_future

    def _fake_ensure_future(coro, *args, **kwargs):
        name = getattr(coro, "__name__", None) or getattr(
            getattr(coro, "cr_code", None), "co_name", ""
        )
        if name == "_connect_and_register":
            scheduled.append(coro)
            coro.close()

            class _Dummy:
                def cancel(self):
                    pass

            return _Dummy()
        return real_ensure_future(coro, *args, **kwargs)

    monkeypatch.setattr(link_manager.asyncio, "ensure_future", _fake_ensure_future)

    async def _run():
        task = asyncio.ensure_future(link_manager._reconnect_loop({}))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.new_event_loop().run_until_complete(_run())

    # Both the DISCONNECTED and PENDING_ACCEPT provisional links should
    # be rescheduled; the CONNECTING one must still be left alone (a
    # fresh connect task is actively in flight for it).
    assert len(scheduled) >= 2, (
        f"expected >=2 reconnects for provisional terminal-state links; "
        f"got {len(scheduled)}"
    )
    # The connecting link was never touched -- its placeholder connect
    # was presumed still mid-flight.
    assert connecting_pending.connects == 0


# ---------------------------------------------------------------------------
# BUG-019: forwarded publish must fire ``salt/job/<jid>/new``
# ---------------------------------------------------------------------------


class _FakePubChan:
    """Minimal :class:`PubServerChannel` stub used by the forward path."""

    def __init__(self):
        self.published = []

    async def publish(self, load):
        self.published.append(dict(load))


class _ForwardWitness:
    """Record every ``_FIRE_EVENT`` and ``chan.publish`` call in order.

    The forward path must fire ``salt/job/<jid>/new`` then
    ``salt/job/<jid>/publish`` BEFORE handing the load to the pub
    channel's IPC write; recording a single ordered list lets a test
    assert that interleaving exactly.
    """

    def __init__(self):
        self.events = []  # list of (kind, tag_or_load_dict)

    def fire(self, tag, data):
        self.events.append(("fire", tag, dict(data)))

    def pub_chan(self):
        witness = self

        class _Chan:
            async def publish(self, load):
                witness.events.append(("publish", dict(load)))

        return _Chan()


def _install_forwarded_publish_fakes(monkeypatch, *, seed_result, mode="async"):
    """Wire the module globals + helpers used by
    :func:`_publish_to_local_minions` to a recording witness.

    ``mode="async"`` installs a fake :data:`_EVENT_BUS` whose
    ``fire_event_async`` records tag + payload (production path).
    ``mode="sync"`` installs only the sync :data:`_FIRE_EVENT` fallback
    (``_EVENT_BUS=None``).  ``mode="unwired"`` leaves both None.
    """
    import salt.topology.link_manager as lm

    witness = _ForwardWitness()
    fake_chan = witness.pub_chan()

    class _FakeEventBus:
        async def fire_event_async(self, data, tag, timeout=1000):
            witness.fire(tag, data)

    monkeypatch.setattr(lm, "_OPTS", {"id": "forward-receiver", "transport": "zeromq"})
    if mode == "async":
        monkeypatch.setattr(lm, "_EVENT_BUS", _FakeEventBus())
        monkeypatch.setattr(lm, "_FIRE_EVENT", None)
    elif mode == "sync":
        monkeypatch.setattr(lm, "_EVENT_BUS", None)
        monkeypatch.setattr(lm, "_FIRE_EVENT", witness.fire)
    else:  # mode == "unwired"
        monkeypatch.setattr(lm, "_EVENT_BUS", None)
        monkeypatch.setattr(lm, "_FIRE_EVENT", None)
    monkeypatch.setattr(lm, "_get_cached_pub_channel", lambda _t, _o: fake_chan)
    monkeypatch.setattr(
        lm,
        "_seed_local_cache_for_forwarded_publish",
        # Accept the optional ``matched`` kwarg added when the pub-ack
        # emission path landed (RFC pub-ack: caller may pre-resolve the
        # local match and pass it in so the seed path reuses the list).
        lambda _load, matched=None: seed_result,
    )
    # ``iter_transport_opts`` normally reads opts; stub it to a single
    # transport pair so the publish loop runs once.  ``link_manager``
    # does a function-local ``import salt.utils.channel`` so patch the
    # module object in ``sys.modules`` directly.
    import salt.utils.channel as _channel_mod

    monkeypatch.setattr(
        _channel_mod,
        "iter_transport_opts",
        lambda _opts: [("zeromq", _opts)],
    )
    # ``strip_cluster_scope`` passthrough so the test target survives.
    monkeypatch.setattr(
        lm.router_mod, "strip_cluster_scope", lambda tgt: tgt, raising=False
    )
    return witness


def _expected_new_job_payload(load, matched):
    return {
        "jid": load["jid"],
        "tgt": load["tgt"],
        "tgt_type": load["tgt_type"],
        "fun": load["fun"],
        "arg": load["arg"],
        "user": load["user"],
        "minions": matched,
        "missing": [],
    }


def test_publish_to_local_minions_fires_new_and_publish_events(monkeypatch):
    """BUG-019 regression: forwarded publish must fire both
    ``salt/job/<jid>/new`` and ``salt/job/<jid>/publish`` on the local
    master event bus, in that order, BEFORE handing the load to
    ``chan.publish``.  Payload shape matches ``_prep_pub``'s
    ``new_job_load`` dict.
    """
    import salt.topology.link_manager as lm

    matched = ["m1", "m2"]
    witness = _install_forwarded_publish_fakes(monkeypatch, seed_result=matched)

    load = {
        "jid": "20261102000000000001",
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
        "user": "root",
    }

    asyncio.new_event_loop().run_until_complete(
        lm._publish_to_local_minions(load)  # pylint: disable=protected-access
    )

    kinds = [e[0] for e in witness.events]
    assert kinds == [
        "fire",
        "fire",
        "publish",
    ], f"expected fire,fire,publish; got {kinds} ({witness.events})"

    new_tag, new_payload = witness.events[0][1], witness.events[0][2]
    pub_tag, pub_payload = witness.events[1][1], witness.events[1][2]
    assert new_tag == "salt/job/20261102000000000001/new"
    assert pub_tag == "salt/job/20261102000000000001/publish"

    expected = _expected_new_job_payload(load, matched)
    assert new_payload == expected
    assert pub_payload == expected


def test_publish_to_local_minions_fires_events_on_empty_match(monkeypatch):
    """BUG-019 edge case: ``_prep_pub`` fires ``salt/job/<jid>/new``
    unconditionally on the origin master (even for publishes with no
    local matches).  The forward path must match that behavior so
    reactors see consistent event flow on every receiving master.
    Minions list in the payload is empty.
    """
    import salt.topology.link_manager as lm

    witness = _install_forwarded_publish_fakes(monkeypatch, seed_result=[])

    load = {
        "jid": "20261102000000000002",
        "tgt": "C@no-such-cluster",
        "tgt_type": "compound",
        "fun": "test.ping",
        "arg": [],
        "user": "root",
    }

    asyncio.new_event_loop().run_until_complete(
        lm._publish_to_local_minions(load)  # pylint: disable=protected-access
    )

    fires = [(e[1], e[2]) for e in witness.events if e[0] == "fire"]
    tags = [t for t, _ in fires]
    assert tags == [
        "salt/job/20261102000000000002/new",
        "salt/job/20261102000000000002/publish",
    ]
    for _, payload in fires:
        assert payload["minions"] == []
        assert payload["missing"] == []


def test_publish_to_local_minions_no_fire_without_wired_hook(monkeypatch):
    """Belt + braces: when neither :data:`_EVENT_BUS` nor
    :data:`_FIRE_EVENT` has been wired (e.g. ``_wire_router_fire_event``
    short-circuited on a test harness with no ``sock_dir``), the forward
    path must silently skip the event-bus fire -- not raise, not try to
    construct a fresh event bus per publish.
    """
    import salt.topology.link_manager as lm  # noqa: F401

    witness = _install_forwarded_publish_fakes(
        monkeypatch, seed_result=["m1"], mode="unwired"
    )

    load = {
        "jid": "20261102000000000003",
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
        "user": "root",
    }

    asyncio.new_event_loop().run_until_complete(
        lm._publish_to_local_minions(load)  # pylint: disable=protected-access
    )

    kinds = [e[0] for e in witness.events]
    assert kinds == [
        "publish"
    ], f"forward path must publish without fires when hook unwired; got {kinds}"


def test_publish_to_local_minions_sync_fire_fallback(monkeypatch):
    """When ``_EVENT_BUS`` is unavailable but the sync ``_FIRE_EVENT``
    hook is wired, the forward path falls back to the sync fire for
    both ``/new`` and ``/publish``.  Guards against regressions that
    tie the forward-fire path exclusively to the async bus.
    """
    import salt.topology.link_manager as lm  # noqa: F401

    matched = ["m1"]
    witness = _install_forwarded_publish_fakes(
        monkeypatch, seed_result=matched, mode="sync"
    )

    load = {
        "jid": "20261102000000000004",
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "arg": [],
        "user": "root",
    }

    asyncio.new_event_loop().run_until_complete(
        lm._publish_to_local_minions(load)  # pylint: disable=protected-access
    )

    kinds = [e[0] for e in witness.events]
    assert kinds == ["fire", "fire", "publish"]
    assert witness.events[0][1] == "salt/job/20261102000000000004/new"
    assert witness.events[1][1] == "salt/job/20261102000000000004/publish"


# ---------------------------------------------------------------------------
# BUG-020: ``_verify_session`` must compare against the inbound record
# ---------------------------------------------------------------------------


def test_verify_session_prefers_inbound_record_over_outbound(clean_state):
    """BUG-020 regression: ``_verify_session`` must compare the
    payload's ``session_generation`` against the server-side
    ``_INBOUND[origin]`` record, not the ``_LINKS[origin]`` outbound
    record.  The two counters are independent -- the inbound record
    tracks the peer's own session gen (received at handshake), the
    outbound tracks this master's session gen for the link where
    *we* initiated the handshake.  Comparing payload gen against
    the outbound side silently rejects every follow-on frame
    whenever the counters have drifted (which they do the moment
    either side bumps generation).  Pre-fix: this frame is dropped
    as "bad/missing session".  Post-fix: accepted.
    """
    # Server-side inbound record for the peer: gen that we received
    # at the peer's handshake.  This is the authoritative counter
    # against which the peer's follow-on frames must be verified.
    inbound_stub = _StubLink("east")
    inbound_stub.session_generation = 3
    link_manager._INBOUND["east"] = inbound_stub  # pylint: disable=protected-access
    # Outbound link we initiated to the same peer, with a different
    # (unrelated) session gen -- our own counter for our own REQ
    # handshake.  Must not interfere with inbound verification.
    outbound_stub = _StubLink("east")
    outbound_stub.session_generation = 1
    link_manager._LINKS["east"] = outbound_stub  # pylint: disable=protected-access

    payload = {
        "tag": "topology/pub",
        "origin_cluster_id": "east",
        "session_generation": 3,  # matches inbound record, NOT outbound
    }
    assert link_manager._verify_session(
        payload
    ), (  # pylint: disable=protected-access
        "frame whose gen matches _INBOUND[origin] must verify"
    )


def test_verify_session_rejects_without_inbound_record(clean_state):
    """BUG-020 negative case: when there is no ``_INBOUND[origin]``
    record (sender's key is not accepted and lazy-register bailed),
    the frame must be rejected -- even when an outbound record
    happens to exist.  The outbound record alone is NOT proof the
    peer is authenticated on the inbound side.
    """
    # Outbound-only: self initiated a connection to east, but east
    # never completed a handshake to self so there is no inbound
    # record.  Verification must fail.
    outbound_stub = _StubLink("east")
    outbound_stub.session_generation = 1
    link_manager._LINKS["east"] = outbound_stub  # pylint: disable=protected-access

    payload = {
        "tag": "topology/pub",
        "origin_cluster_id": "east",
        "session_generation": 1,
    }
    assert not link_manager._verify_session(  # pylint: disable=protected-access
        payload
    ), (
        "frame with no _INBOUND[origin] record must be rejected regardless of "
        "any outbound record"
    )


def test_verify_session_rejects_stale_inbound_gen(clean_state):
    """BUG-020 regression: strict equality against the inbound
    record is preserved.  A replayed frame with an older gen than
    the inbound-cached gen (which :func:`_maybe_lazy_register_inbound`
    only ever bumps forward) must still be rejected.
    """
    inbound_stub = _StubLink("east")
    inbound_stub.session_generation = 5
    link_manager._INBOUND["east"] = inbound_stub  # pylint: disable=protected-access

    payload = {
        "tag": "topology/pub",
        "origin_cluster_id": "east",
        "session_generation": 1,  # replay / stale
    }
    assert not link_manager._verify_session(  # pylint: disable=protected-access
        payload
    ), "stale-gen replay against bumped _INBOUND must still be rejected"


def test_verify_session_master_auth_bypass_preserved(clean_state):
    """``_master_auth`` frames carry no session yet -- they ARE the
    handshake.  The receiver must always pass them through to
    :func:`_handle_master_auth` for key acceptance, regardless of
    the inbound record state.
    """
    for tag in ("_master_auth", "topology/_master_auth"):
        payload = {"tag": tag, "origin_cluster_id": "east"}
        assert link_manager._verify_session(  # pylint: disable=protected-access
            payload
        ), f"{tag} must bypass session check"


# ---------------------------------------------------------------------------
# BUG-022: cluster_pki_dir must be consulted for topology peer keys
# ---------------------------------------------------------------------------


def test_masters_subdir_prefers_cluster_pki_dir_when_cluster_id_set(tmp_path):
    """BUG-022 (ROOT CAUSE): on a clustered 3008.x master,
    :func:`_masters_subdir` MUST resolve ``masters``/``masters_pre``/etc
    against ``cluster_pki_dir``, NOT ``pki_dir``.

    Pre-accepted topology peer keys are seeded under ``cluster_pki_dir``
    so all N replicas in a cluster share the accept state.  Pre-fix the
    topology module looked only at ``pki_dir`` and so could never find
    those pre-accepted keys -- every handshake returned ``status=retry``
    on every attempt, parking the mesh at ``configured``/``pending``
    forever.
    """
    cluster_pki = tmp_path / "cluster-pki"
    pki = tmp_path / "pki"
    cluster_pki.mkdir()
    pki.mkdir()
    opts = {
        "cluster_id": "east",
        "cluster_pki_dir": str(cluster_pki),
        "pki_dir": str(pki),
    }
    result = link_manager._masters_subdir(  # pylint: disable=protected-access
        opts, "masters"
    )
    assert result == str(cluster_pki / "masters")


def test_masters_subdir_falls_back_to_pki_dir_for_solo_master(tmp_path):
    """A solo master (no ``cluster_id``) uses ``pki_dir/masters``."""
    pki = tmp_path / "pki"
    pki.mkdir()
    opts = {
        "pki_dir": str(pki),
    }
    result = link_manager._masters_subdir(  # pylint: disable=protected-access
        opts, "masters"
    )
    assert result == str(pki / "masters")


def test_handle_master_auth_accepts_key_in_cluster_pki_dir(
    opts, clean_state, monkeypatch, tmp_path
):
    """BUG-022: when the receiver is clustered and the peer's key lives
    at ``<cluster_pki_dir>/masters/<cluster_id>.pub``,
    :func:`_handle_master_auth` MUST return ``status=ok`` (not
    ``status=retry``) and populate ``_INBOUND[cluster_id]``.
    """
    cluster_pki = tmp_path / "cluster-pki-recv"
    cluster_pki.mkdir()
    (cluster_pki / "masters").mkdir()
    accepted = cluster_pki / "masters" / "east.pub"
    accepted.write_bytes(
        b"-----BEGIN PUBLIC KEY-----\npeer-east-key\n-----END PUBLIC KEY-----\n"
    )
    cluster_opts = dict(opts)
    cluster_opts["cluster_id"] = "self"
    cluster_opts["cluster_pki_dir"] = str(cluster_pki)
    monkeypatch.setattr(link_manager, "_OPTS", cluster_opts)

    load = {"cluster_id": "east", "nonce": "deadbeef"}
    reply = asyncio.new_event_loop().run_until_complete(
        link_manager._handle_master_auth(load)  # pylint: disable=protected-access
    )
    assert reply["status"] == "ok", (
        f"Pre-fix: receiver looked only at pki_dir/masters/east.pub and "
        f"returned status=retry.  Post-fix: looks at "
        f"cluster_pki_dir/masters/east.pub and returns ok.  Got: {reply}"
    )
    assert (
        "east" in link_manager._INBOUND  # pylint: disable=protected-access
    ), "post-fix must populate _INBOUND after accept"


def test_inbound_listener_bypasses_cluster_ready_gate(opts, clean_state, monkeypatch):
    """BUG-022: the inbound topology ``ReqServerChannel`` MUST be built
    with ``cluster_peers=[]`` in its channel-opts so that
    :func:`salt.channel.server._cluster_is_ready` short-circuits True.

    The topology peer handshake is a key-on-disk identity exchange that
    must work BEFORE Raft commits (startup) and must stay functional
    through Raft flaps.  Pre-fix the listener inherited
    ``cluster_peers`` from the master's opts and so the gate blocked
    every inbound ``topology/_master_auth`` with a ``cluster_retry``
    reply --- the sender's handshake never reached
    :func:`_handle_master_auth`, so handshakes stayed stuck at
    ``pending`` forever on 3-master clusters.
    """
    captured_opts = {}

    class _FakeReqServerChannel:
        @classmethod
        def factory(cls, chan_opts):
            captured_opts.update(chan_opts)
            inst = cls()
            inst.post_fork = lambda handler, loop, **kwargs: None
            return inst

    import salt.channel.server

    monkeypatch.setattr(salt.channel.server, "ReqServerChannel", _FakeReqServerChannel)
    # Prime the clustered-master shape so the fixture resembles the sandbox.
    cluster_opts = dict(opts)
    cluster_opts["cluster_peers"] = ["10.0.0.2", "10.0.0.3"]
    cluster_opts["cluster_id"] = "self"

    loop = asyncio.new_event_loop()
    try:
        result = (
            link_manager._open_inbound_listener(  # pylint: disable=protected-access
                cluster_opts, loop
            )
        )
    finally:
        loop.close()

    assert result is not None, "inbound listener build failed"
    assert captured_opts.get("cluster_peers") == [], (
        f"inbound topology listener MUST zero cluster_peers so the "
        f"_cluster_is_ready gate short-circuits True; got "
        f"{captured_opts.get('cluster_peers')!r}"
    )


def test_handle_master_auth_writes_pending_to_cluster_pki_dir(
    opts, clean_state, monkeypatch, tmp_path
):
    """BUG-022: when no accepted key exists, the receiver must write
    the pending-key sentinel under ``<cluster_pki_dir>/masters_pre/``
    (NOT ``pki_dir/masters_pre/``) so all cluster replicas see the
    same pending state.
    """
    cluster_pki = tmp_path / "cluster-pki-recv2"
    cluster_pki.mkdir()
    cluster_opts = dict(opts)
    cluster_opts["cluster_id"] = "self"
    cluster_opts["cluster_pki_dir"] = str(cluster_pki)
    monkeypatch.setattr(link_manager, "_OPTS", cluster_opts)

    load = {
        "cluster_id": "east",
        "nonce": "deadbeef",
        "public_key": b"-----BEGIN PUBLIC KEY-----\neast-id\n-----END PUBLIC KEY-----\n",
    }
    reply = asyncio.new_event_loop().run_until_complete(
        link_manager._handle_master_auth(load)  # pylint: disable=protected-access
    )
    assert reply["status"] == "retry"
    pending_path = cluster_pki / "masters_pre" / "east.pub"
    assert pending_path.exists(), (
        f"pending-key sentinel must land under cluster_pki_dir/masters_pre; "
        f"got nothing at {pending_path}"
    )
    assert pending_path.read_bytes() == load["public_key"], (
        "pending-key file must carry the sender's public_key bytes "
        "(pre-fix: handshake load omitted public_key -> zero-byte file)"
    )
