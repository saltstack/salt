"""
Unit tests for the Phase 5 pub-daemon topology hooks and the
MWorker-side ``_return`` envelope hand-off.

These are pure-logic tests that complement
:file:`tests/pytests/functional/topology/test_pub_daemon_hooks.py`.
They cover:

* Guard-clause behavior: every hook is a strict no-op when
  ``topology_enabled`` is not set.
* Envelope-based topology detection in ``AESFuncs._return`` /
  ``_sync_return``: the detection must use ``load["topology"]["origin"]``,
  NOT ``load["jid"]`` string parsing.  This is critical for compatibility
  with Salt's native jid formats, ``unique_jid: True`` deployments, and
  side-by-side syndic coexistence --- all of which keep the jid in its
  native Salt shape, with no cluster prefix.
* Exception propagation: hook bodies must not swallow unrelated
  programmer errors silently; however, a topology-side failure (bad
  envelope, breadcrumb cache error, event bus error) must never fail
  the local return path.
"""

import pytest

import salt.channel.server
import salt.master
import salt.topology.breadcrumbs as breadcrumbs
from tests.support.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _bare_channel(opts, topology_enabled):
    """Minimal MasterPubServerChannel instance bypassing ``factory``."""
    inst = salt.channel.server.MasterPubServerChannel.__new__(
        salt.channel.server.MasterPubServerChannel
    )
    inst.opts = dict(opts)
    inst.opts["topology_enabled"] = topology_enabled
    inst.transport = MagicMock()
    inst.transport.close = MagicMock()
    inst._raft_dispatcher = None
    inst._raft_service = None
    inst.pushers = []
    inst.peer_keys = {}
    inst.cluster_peers = []
    inst._discover_event = None
    inst._discover_token = None
    inst._discover_candidates = {}
    return inst


def _aes_funcs_stub(opts):
    inst = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    inst.opts = opts
    inst.event = MagicMock()
    inst.event.fire_master = MagicMock()
    inst.event.fire_event = MagicMock()
    inst.event.fire_event_async = AsyncMock()
    inst.mminion = MagicMock()
    inst.key_cache = MagicMock()
    inst.ckminions = MagicMock()
    inst.local = MagicMock()
    inst.fs_ = MagicMock()
    inst.masterapi = MagicMock()
    inst.cache = MagicMock()
    inst.pki_dir = opts.get("pki_dir", "")
    inst.async_methods = ()
    return inst


@pytest.fixture
def minimal_opts(tmp_path):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "id": "unit-master",
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
        "cluster_id": "",
        "cluster_peers": [],
        "interface": "127.0.0.1",
        "topology_enabled": False,
        "topology_link_port": 44520,
        "topology_breadcrumb_grace": 5,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 256,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 256,
        "topology_registry_cache_key_size": 64,
        "require_minion_sign_messages": False,
        "drop_messages_signature_fail": False,
        "signing_algorithm": "sha256",
        "master_job_cache": "local_cache",
        "keys.cache_driver": "localfs",
        "job_cache": True,
    }


# ===========================================================================
# Guard-clause coverage for every hook
# ===========================================================================


def test_pre_fork_disabled_does_not_import_link_manager(minimal_opts):
    """``topology_enabled=False`` -> ``link_manager.pre_fork`` not called."""
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    inst.transport.publish_daemon = MagicMock()

    with patch("salt.topology.link_manager.pre_fork") as pre_fork_mock:
        inst.pre_fork(MagicMock())

    pre_fork_mock.assert_not_called()


def test_close_disabled_does_not_import_link_manager(minimal_opts):
    """Closing a non-topology master never pulls in link_manager."""
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    with patch("salt.topology.link_manager.stop") as stop_mock:
        inst.close()
    stop_mock.assert_not_called()
    inst.transport.close.assert_called_once()


def test_sync_return_disabled_does_not_touch_topology(minimal_opts):
    """
    When ``topology_enabled`` is not set, ``_sync_return`` must not
    import :mod:`salt.topology.breadcrumbs` nor fire a topology event.
    """
    inst = _aes_funcs_stub(minimal_opts)
    load = {
        "id": "minion-01",
        "jid": "20260101000000000100",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        # Even with an envelope present, disabled topology ignores it.
        "topology": {"origin": "west"},
    }
    with patch("salt.topology.breadcrumbs.open_reader") as reader, patch(
        "salt.utils.job.store_job"
    ):
        inst._sync_return(load)

    reader.assert_not_called()
    for call in inst.event.fire_event.call_args_list:
        tag = call.args[1] if len(call.args) > 1 else ""
        assert not str(tag).startswith("salt/topology/return/")


def test_async_return_disabled_does_not_touch_topology(minimal_opts):
    """Async-path guard clause mirrors the sync-path."""
    import asyncio as _asyncio

    inst = _aes_funcs_stub(minimal_opts)
    load = {
        "id": "minion-01",
        "jid": "20260101000000000101",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "west"},
    }

    async def _run():
        with patch("salt.topology.breadcrumbs.open_reader") as reader, patch(
            "salt.utils.job.store_job"
        ):
            await inst._return(load)
        return reader

    reader = _asyncio.run(_run())
    reader.assert_not_called()


# ===========================================================================
# Envelope-based detection: NOT jid-string parsing
# ===========================================================================


def _return_opts(tmp_path, cluster_id="east"):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "id": "unit-master",
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 5,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 256,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 256,
        "topology_registry_cache_key_size": 64,
        "require_minion_sign_messages": False,
        "drop_messages_signature_fail": False,
        "signing_algorithm": "sha256",
        "master_job_cache": "local_cache",
        "keys.cache_driver": "localfs",
        "job_cache": True,
    }


@pytest.mark.parametrize(
    "jid",
    [
        # Native 20-digit microsecond jid; no cluster prefix.
        "20260101000000000001",
        # Short/unique_jid style; still no cluster prefix.
        "abc123",
        # Legacy numeric; no cluster prefix.
        "1735689600000000",
    ],
)
def test_sync_return_envelope_detection_ignores_jid_shape(tmp_path, jid):
    """
    Detection pivots entirely on ``load["topology"]["origin"]``.  No jid
    shape --- native, unique_jid, or legacy --- is parsed to decide
    whether this is a topology return.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    # Record a breadcrumb for the jid so the lookup succeeds.
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    breadcrumbs.put(writer, jid, "west", publish_timeout=5, opts=opts)
    writer.close()

    inst = _aes_funcs_stub(opts)
    load = {
        "id": "minion-01",
        "jid": jid,
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "west"},
    }

    with patch("salt.utils.job.store_job"):
        inst._sync_return(load)

    tags = [call.args[1] for call in inst.event.fire_event.call_args_list]
    assert any(
        t == f"salt/topology/return/west/{jid}" for t in tags
    ), f"topology event tag not fired for jid={jid!r}; saw {tags!r}"


def test_sync_return_without_envelope_never_parses_jid(tmp_path):
    """
    A return with NO topology envelope must not even open the breadcrumb
    cache --- that proves detection is envelope-first, not jid-parsing.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    inst = _aes_funcs_stub(opts)

    # jid intentionally shaped to look like a cluster-prefixed string so
    # a naive implementation would try to parse it.
    load = {
        "id": "minion-01",
        "jid": "west:20260101000000000001",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
    }

    with patch("salt.topology.breadcrumbs.open_reader") as reader, patch(
        "salt.utils.job.store_job"
    ):
        inst._sync_return(load)

    assert not reader.called, (
        "_sync_return opened the breadcrumb reader for a non-topology return; "
        "detection may be falling back to jid-string parsing"
    )


def test_sync_return_origin_is_only_decision_input(tmp_path):
    """
    If origin == self.opts["cluster_id"], the hand-off is suppressed
    regardless of any other hint.  Proves ``origin`` is the gate, not
    any attribute of ``load["jid"]``.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    jid = "20260101000000000050"
    breadcrumbs.put(writer, jid, "west", publish_timeout=5, opts=opts)
    writer.close()

    inst = _aes_funcs_stub(opts)
    load = {
        "id": "minion-01",
        "jid": jid,  # breadcrumb exists --- but origin==self must still skip
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "east"},
    }

    with patch("salt.utils.job.store_job"):
        inst._sync_return(load)

    for call in inst.event.fire_event.call_args_list:
        tag = call.args[1] if len(call.args) > 1 else ""
        assert not str(tag).startswith("salt/topology/return/")


# ===========================================================================
# Exception propagation and side-effect isolation
# ===========================================================================


def test_sync_return_topology_hand_off_failure_does_not_break_store_job(tmp_path):
    """
    A failure inside the topology hand-off (e.g. breadcrumb cache open
    raises) must not raise out of ``_sync_return`` --- the local store
    path is authoritative, and operators would rather lose the
    upstream forward than lose the local return.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    inst = _aes_funcs_stub(opts)

    load = {
        "id": "minion-01",
        "jid": "20260101000000000060",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "west"},
    }

    with patch("salt.utils.job.store_job") as store_job, patch(
        "salt.topology.breadcrumbs.open_reader",
        side_effect=RuntimeError("mmap boom"),
    ):
        # Must NOT raise.
        inst._sync_return(load)

    # Local store still ran before/with hand-off.
    store_job.assert_called_once()


def test_pre_fork_hook_exception_propagates_from_implementation(minimal_opts):
    """
    Programmer-error failures inside ``link_manager.pre_fork`` must
    propagate --- the hook itself is NOT allowed to swallow them.
    (The alternative is silent misconfiguration that only surfaces as
    missing links at publish time.)
    """
    inst = _bare_channel(minimal_opts, topology_enabled=True)
    inst.transport.publish_daemon = MagicMock()

    with patch(
        "salt.topology.link_manager.pre_fork",
        side_effect=RuntimeError("link_manager boom"),
    ):
        with pytest.raises(RuntimeError, match="link_manager boom"):
            inst.pre_fork(MagicMock())


def test_pre_fork_hook_disabled_never_raises(minimal_opts):
    """
    The topology-disabled path is a bare ``if``; even if
    ``link_manager.pre_fork`` would raise, the guard must prevent that
    from happening because the import does not occur.
    """
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    inst.transport.publish_daemon = MagicMock()

    with patch(
        "salt.topology.link_manager.pre_fork",
        side_effect=RuntimeError("should never run"),
    ):
        # No exception --- the guard clips the import before the raise.
        inst.pre_fork(MagicMock())
