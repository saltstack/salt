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
