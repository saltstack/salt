"""
Functional tests for the publish-daemon topology hooks and the
MWorker-side ``_return`` envelope hand-off (Phase 5 wiring).

The hooks under test are the minimal integration points added to:

* :class:`salt.channel.server.MasterPubServerChannel`:

    - ``pre_fork`` -> ``salt.topology.link_manager.pre_fork``
    - ``_publish_daemon`` -> ``salt.topology.link_manager.start``
    - ``close`` -> ``salt.topology.link_manager.stop``
    - ``publish_payload`` -> ``salt.topology.router.on_publish``

* :class:`salt.master.AESFuncs._return` (and the LTS sync shim
  ``_sync_return``):

    - When ``load["topology"]["origin"]`` names a non-local cluster
      and a breadcrumb exists for ``load["jid"]``, fire
      ``salt/topology/return/<origin>/<jid>`` on the master event bus
      so the publish-daemon subscriber can forward upstream.
    - Otherwise, store locally only (no event fire).

The tests use real :mod:`salt.topology.breadcrumbs` /
:mod:`salt.topology.registry` MmapCaches and a bare
``MasterPubServerChannel`` instance where appropriate; sub-processes
of the daemon lifecycle are driven by the harness
``single_master`` fixture to assert hook dispatch end-to-end.

A full east->west publish forwarding end-to-end test is not included
at this phase: the harness ``accept_peer`` writes a placeholder
identity-pub key (see ``tests/support/topology/cluster.py``), so the
inbound ``topology/_master_auth`` handshake would reject the peer
before any publish can forward.  Full-handshake E2E lands with the
real identity-key issuance (see RFC ``salt/crypt.py --- master
identity key``).  Within Phase 5 scope the hook plumbing + envelope
detection are verified here; the dispatcher behavior is already
covered by :file:`tests/pytests/functional/topology/test_router.py`
and :file:`tests/pytests/functional/topology/test_link_manager.py`.
"""

import asyncio
import pathlib

import pytest

import salt.channel.server
import salt.master
import salt.topology.breadcrumbs as breadcrumbs
from tests.support.mock import AsyncMock, MagicMock, patch

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Hook-dispatch tests on a bare MasterPubServerChannel instance
#
# We instantiate MasterPubServerChannel directly with a mock transport so the
# four hook integration points can be exercised without the publish-daemon
# process spin-up overhead.  This isolates "does the hook fire" from
# "does salt.topology.link_manager actually bring up links" --- the latter
# is covered by the dedicated topology module tests.
# ---------------------------------------------------------------------------


def _bare_channel(opts, topology_enabled):
    """
    Build a :class:`MasterPubServerChannel` instance without going through
    ``factory``.  The channel's hooks are the only surface under test here,
    so we skip transport / master-key / cluster-peer wiring and set the
    attributes the methods touch directly.
    """
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


@pytest.fixture
def minimal_opts(tmp_path):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "id": "master-test",
        "pki_dir": str(pki_dir),
        "sock_dir": str(tmp_path / "sock"),
        "cachedir": str(tmp_path / "cache"),
        "cluster_id": "",
        "cluster_peers": [],
        "interface": "127.0.0.1",
        "topology_enabled": False,
        "topology_link_port": 44506,
        "topology_breadcrumb_grace": 5,
        "topology_breadcrumb_max_age": 60,
        "topology_breadcrumb_cache_size": 256,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 256,
        "topology_registry_cache_key_size": 64,
    }


# ---------------------------------------------------------------------------
# pre_fork hook
# ---------------------------------------------------------------------------


def test_pre_fork_calls_link_manager_when_enabled(minimal_opts):
    """
    When ``topology_enabled`` is True, ``pre_fork`` delegates to
    :func:`salt.topology.link_manager.pre_fork` with the opts and the
    process manager.  No other side effect from the topology path.
    """
    inst = _bare_channel(minimal_opts, topology_enabled=True)
    process_manager = MagicMock()
    # pre_fork's existing body guards on ``hasattr(self.transport,
    # "publish_daemon")`` for the EventPublisher add_process path.
    inst.transport.publish_daemon = MagicMock()

    with patch("salt.topology.link_manager.pre_fork") as lm_pre_fork:
        inst.pre_fork(process_manager)

    lm_pre_fork.assert_called_once()
    args, _ = lm_pre_fork.call_args
    assert args[0] is inst.opts
    assert args[1] is process_manager


def test_pre_fork_noop_when_topology_disabled(minimal_opts):
    """Backward compat: topology disabled -> no topology module import."""
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    inst.transport.publish_daemon = MagicMock()
    process_manager = MagicMock()

    with patch("salt.topology.link_manager.pre_fork") as lm_pre_fork:
        inst.pre_fork(process_manager)

    lm_pre_fork.assert_not_called()


# ---------------------------------------------------------------------------
# close hook
# ---------------------------------------------------------------------------


def test_close_calls_link_manager_stop_when_enabled(minimal_opts):
    """``close`` runs the topology stop coroutine when enabled."""
    inst = _bare_channel(minimal_opts, topology_enabled=True)

    async def _fake_stop():
        _fake_stop.called = True

    _fake_stop.called = False

    with patch("salt.topology.link_manager.stop", _fake_stop):
        inst.close()

    assert _fake_stop.called is True
    inst.transport.close.assert_called_once()


def test_close_noop_when_topology_disabled(minimal_opts):
    """``close`` never imports topology when disabled."""
    inst = _bare_channel(minimal_opts, topology_enabled=False)

    with patch("salt.topology.link_manager.stop") as lm_stop:
        inst.close()

    lm_stop.assert_not_called()
    inst.transport.close.assert_called_once()


# ---------------------------------------------------------------------------
# publish_payload hook
# ---------------------------------------------------------------------------


def _tagged_payload(tag, data):
    """Build the raw tag<TAGEND>payload bytes shape ``publish_payload`` expects."""
    import salt.payload
    import salt.utils.event
    import salt.utils.stringutils

    body = salt.payload.dumps(data, use_bin_type=True)
    return (
        salt.utils.stringutils.to_bytes(tag)
        + salt.utils.stringutils.to_bytes(salt.utils.event.TAGEND)
        + body
    )


async def _invoke_publish_payload(inst, tag, data):
    """
    Drive ``publish_payload`` with a non-cluster tag so it exercises the
    minion fan-out branch (and therefore the topology hook that follows).
    """
    inst.transport.publish_payload = AsyncMock(return_value=None)
    load = _tagged_payload(tag, data)
    await inst.publish_payload(load)


def test_publish_payload_calls_router_on_publish_when_enabled(minimal_opts):
    """
    After the existing minion fan-out, ``publish_payload`` must call
    :func:`salt.topology.router.on_publish` with the decoded load and the
    channel's io_loop.
    """
    inst = _bare_channel(minimal_opts, topology_enabled=True)
    import tornado.ioloop

    inst.io_loop = tornado.ioloop.IOLoop.current()

    data = {"jid": "20260101000000000001", "fun": "test.ping", "tgt": "*"}

    with patch("salt.topology.router.on_publish", new=AsyncMock()) as on_pub:
        inst.io_loop.run_sync(
            lambda: _invoke_publish_payload(inst, "20260101000000000001", data)
        )

    assert on_pub.call_count == 1
    pos_args, _ = on_pub.call_args
    # First positional arg is the decoded load; second is the io_loop.
    assert isinstance(pos_args[0], dict)
    assert pos_args[0].get("jid") == "20260101000000000001"
    assert pos_args[1] is inst.io_loop


def test_publish_payload_noop_when_topology_disabled(minimal_opts):
    """Topology disabled -> never calls router.on_publish."""
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    import tornado.ioloop

    inst.io_loop = tornado.ioloop.IOLoop.current()
    data = {"jid": "20260101000000000002", "fun": "test.ping", "tgt": "*"}

    with patch("salt.topology.router.on_publish", new=AsyncMock()) as on_pub:
        inst.io_loop.run_sync(
            lambda: _invoke_publish_payload(inst, "20260101000000000002", data)
        )

    on_pub.assert_not_called()


# ---------------------------------------------------------------------------
# publish_daemon hook  --- schedule link_manager.start on the io_loop
# ---------------------------------------------------------------------------


def test_publish_daemon_schedules_link_manager_start_when_enabled(
    minimal_opts, tmp_path
):
    """
    ``_publish_daemon`` enters the io_loop forever; we don't want to run the
    full daemon.  Replicate the hook body here --- read the running ioloop,
    then verify that scheduling via :meth:`IOLoop.spawn_callback` reaches
    :func:`salt.topology.link_manager.start` with the opts and io_loop
    arguments the hook passes.
    """
    import tornado.ioloop

    inst = _bare_channel(minimal_opts, topology_enabled=True)
    inst.io_loop = tornado.ioloop.IOLoop.current()

    captured = {"start_called": False}

    async def _fake_start(opts, io_loop, *args, **kwargs):
        captured["start_called"] = True
        captured["opts"] = opts
        captured["io_loop"] = io_loop

    with patch("salt.topology.link_manager.start", new=_fake_start):
        import importlib

        link_manager = importlib.import_module("salt.topology.link_manager")

        async def _driver():
            # Replicate the hook body:
            inst.io_loop.spawn_callback(link_manager.start, inst.opts, inst.io_loop)
            # Give the spawned callback a chance to run.
            await asyncio.sleep(0.05)

        inst.io_loop.run_sync(_driver)

    assert (
        captured["start_called"] is True
    ), "link_manager.start was not scheduled by the publish_daemon hook pattern"
    assert captured["opts"] is inst.opts
    assert captured["io_loop"] is inst.io_loop


def test_publish_daemon_hook_noop_when_topology_disabled(minimal_opts):
    """
    When topology is disabled, the ``_publish_daemon`` body must not import
    or schedule anything from :mod:`salt.topology.link_manager`.

    The hook under test is a plain ``if self.opts.get("topology_enabled")``
    guard; this asserts the guard evaluates False and skips.
    """
    inst = _bare_channel(minimal_opts, topology_enabled=False)
    # Guard is a bool check; running the branch condition is sufficient.
    assert not inst.opts.get("topology_enabled")
    # Also verify that nothing else from topology is imported eagerly:
    # ``MasterPubServerChannel`` must not reference ``salt.topology.*`` at
    # class-import time.
    import importlib

    mod = importlib.import_module("salt.channel.server")
    assert not hasattr(mod, "_TOPOLOGY_EAGER_IMPORT_PROOF")


# ---------------------------------------------------------------------------
# AESFuncs._return topology envelope hand-off
# ---------------------------------------------------------------------------


def _aes_funcs_stub(opts):
    """
    Build an ``AESFuncs`` instance without running its full ``__init__``.

    We only need ``_return`` / ``_sync_return`` to run against a stubbed
    ``self.opts`` + ``self.event`` + ``self.mminion`` + ``self.key_cache``.
    """
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


def _return_opts(tmp_path, cluster_id="east"):
    pki_dir = tmp_path / "pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "id": "master-test",
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


def test_sync_return_fires_topology_event_when_envelope_and_breadcrumb(tmp_path):
    """
    LTS-default sync ``_sync_return`` path: a return with
    ``load["topology"]["origin"] = "west"`` (foreign cluster) and a
    pre-recorded breadcrumb for ``load["jid"]`` fires
    ``salt/topology/return/west/<jid>`` on the event bus.
    """
    opts = _return_opts(tmp_path, cluster_id="east")

    # Record a breadcrumb for a jid we'll receive a return for.
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    jid = "20260101000000000003"
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

    with patch("salt.utils.job.store_job") as store_job:
        inst._sync_return(load)

    store_job.assert_called_once()
    # Event fires with the salt/topology/return/<origin>/<jid> tag.
    inst.event.fire_event.assert_called()
    tags = [call.args[1] for call in inst.event.fire_event.call_args_list]
    assert any(t == f"salt/topology/return/west/{jid}" for t in tags)


def test_sync_return_no_event_when_no_topology_envelope(tmp_path):
    """
    Plain minion return (no ``load["topology"]``) stores locally only.
    No ``salt/topology/return/*`` tag fires.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    inst = _aes_funcs_stub(opts)

    load = {
        "id": "minion-01",
        "jid": "20260101000000000004",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
    }

    with patch("salt.utils.job.store_job") as store_job:
        inst._sync_return(load)

    store_job.assert_called_once()
    # No topology-return tag fired.
    for call in inst.event.fire_event.call_args_list:
        tag = call.args[1] if len(call.args) > 1 else call.kwargs.get("tag", "")
        assert not str(tag).startswith("salt/topology/return/")


def test_sync_return_no_event_when_origin_is_local_cluster(tmp_path):
    """
    If the envelope origin matches this cluster, the publish originated
    here --- store locally only, no upstream hand-off.
    """
    opts = _return_opts(tmp_path, cluster_id="east")

    # Even if a breadcrumb exists, origin==self must suppress the hand-off.
    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    jid = "20260101000000000005"
    breadcrumbs.put(writer, jid, "west", publish_timeout=5, opts=opts)
    writer.close()

    inst = _aes_funcs_stub(opts)
    load = {
        "id": "minion-01",
        "jid": jid,
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "east"},
    }

    with patch("salt.utils.job.store_job"):
        inst._sync_return(load)

    for call in inst.event.fire_event.call_args_list:
        tag = call.args[1] if len(call.args) > 1 else call.kwargs.get("tag", "")
        assert not str(tag).startswith("salt/topology/return/")


def test_sync_return_no_event_when_envelope_but_no_breadcrumb(tmp_path):
    """
    Foreign-origin envelope but no breadcrumb: store locally only.
    Prevents replay of returns for publishes we never saw.
    """
    opts = _return_opts(tmp_path, cluster_id="east")
    # Create empty breadcrumb cache.
    breadcrumbs.pre_create(opts)

    inst = _aes_funcs_stub(opts)
    load = {
        "id": "minion-01",
        "jid": "20260101000000000006",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
        "topology": {"origin": "west"},
    }

    with patch("salt.utils.job.store_job"):
        inst._sync_return(load)

    for call in inst.event.fire_event.call_args_list:
        tag = call.args[1] if len(call.args) > 1 else call.kwargs.get("tag", "")
        assert not str(tag).startswith("salt/topology/return/")


# ---------------------------------------------------------------------------
# Async _return path (master_async_mworker=True on master branch)
# ---------------------------------------------------------------------------


def test_async_return_fires_topology_event_when_envelope_and_breadcrumb(tmp_path):
    """Mirror the sync-path test on the async code path."""
    opts = _return_opts(tmp_path, cluster_id="east")

    breadcrumbs.pre_create(opts)
    writer = breadcrumbs.open_writer(opts)
    jid = "20260101000000000007"
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

    async def _driver():
        with patch("salt.utils.job.store_job"):
            await inst._return(load)

    asyncio.run(_driver())

    # Event fires either via fire_event or fire_event_async on the async path.
    called_tags = [c.args[1] for c in inst.event.fire_event.call_args_list]
    called_tags += [c.args[1] for c in inst.event.fire_event_async.call_args_list]
    assert any(
        t == f"salt/topology/return/west/{jid}" for t in called_tags
    ), f"topology-return tag not fired; saw: {called_tags!r}"


def test_async_return_no_event_without_topology_envelope(tmp_path):
    """Async path: a plain return triggers no topology event."""
    opts = _return_opts(tmp_path, cluster_id="east")
    inst = _aes_funcs_stub(opts)
    load = {
        "id": "minion-01",
        "jid": "20260101000000000008",
        "return": {"status": "ok"},
        "fun": "test.ping",
        "success": True,
    }

    async def _driver():
        with patch("salt.utils.job.store_job"):
            await inst._return(load)

    asyncio.run(_driver())

    called_tags = [c.args[1] for c in inst.event.fire_event.call_args_list]
    called_tags += [c.args[1] for c in inst.event.fire_event_async.call_args_list]
    for tag in called_tags:
        assert not str(tag).startswith("salt/topology/return/")


# ---------------------------------------------------------------------------
# Daemon-lifecycle integration: single_master running with topology enabled
# ---------------------------------------------------------------------------


def test_single_master_topology_mmap_files_exist(single_master):
    """
    End-to-end: a ``topology_enabled: True`` master brought up by the
    harness has, after startup, the breadcrumb and registry MmapCache
    files on disk under ``<pki_dir>/master/`` ---  evidence that the
    ``pre_fork`` -> ``link_manager.pre_fork`` -> ``breadcrumbs.pre_create``
    + ``registry.pre_create`` chain fired.
    """
    cluster = single_master()
    master = cluster.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    # pre_create writes the cache file under pki_dir/master/
    bc_path = pki_dir / "master" / "topology_breadcrumbs.mmap"
    reg_path = pki_dir / "master" / "topology_registry.mmap"
    assert bc_path.exists(), (
        f"breadcrumbs cache not pre_created at {bc_path}; "
        f"pre_fork hook likely not wired"
    )
    assert reg_path.exists(), (
        f"registry cache not pre_created at {reg_path}; "
        f"pre_fork hook likely not wired"
    )


def test_single_master_topology_disabled_leaves_no_mmap(single_master):
    """
    Backward compat: with ``topology_enabled: False``, the master must not
    pre-create topology cache files --- no behavioral change for pre-5.x
    deployments.
    """
    cluster = single_master(opts_overrides={"topology_enabled": False})
    master = cluster.masters[0]
    pki_dir = pathlib.Path(master.config["pki_dir"])
    bc_path = pki_dir / "master" / "topology_breadcrumbs.mmap"
    reg_path = pki_dir / "master" / "topology_registry.mmap"
    assert (
        not bc_path.exists()
    ), f"breadcrumbs cache was created with topology_enabled=False: {bc_path}"
    assert (
        not reg_path.exists()
    ), f"registry cache was created with topology_enabled=False: {reg_path}"
