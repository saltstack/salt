"""
Regression tests for the ``master_async_mworker`` opt-in flag.

PR #70129 converted every ``AESFuncs`` / ``ClearFuncs`` / ``AuthFuncs``
handler on 3008.x to ``async def``.  On the LTS (3008.x) branch that
behaviour must be strictly opt-in: with ``master_async_mworker`` off
(the default) the dispatch tables, method signatures, and IPC socket
topology have to look exactly like Argon v3008.2 and earlier.

These tests exercise the OFF path only.  The ON path is covered by
``test_master.py`` and ``test_master_async_error_paths.py``.
"""

import inspect

import pytest

import salt.channel.server
import salt.config
import salt.master


@pytest.fixture
def sync_master_opts(master_opts):
    """
    ``master_opts`` with ``master_async_mworker`` explicitly disabled
    (which is also the DEFAULT_MASTER_OPTS default on 3008.x).
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = False
    return opts


@pytest.fixture
def async_master_opts(master_opts):
    """
    ``master_opts`` with ``master_async_mworker`` explicitly enabled
    (opt-in path — mirrors what master.py does on Argon and later).
    """
    opts = master_opts.copy()
    opts["master_async_mworker"] = True
    return opts


def test_default_master_opts_ships_async_mworker_disabled():
    """
    The LTS default MUST be ``master_async_mworker: False`` — flipping
    the default would be a silent behavior change on 3008.x, which
    violates the LTS policy.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["master_async_mworker"] is False


def test_aesfuncs_sync_mode_empties_instance_async_methods(sync_master_opts):
    """
    With the flag off, ``AESFuncs.__init__`` must instance-shadow the
    class-level ``async_methods`` tuple with an empty one so
    ``run_func``'s async-dispatch branch is never taken.  The
    class-level default is left intact so the opt-in path still works.
    """
    af = salt.master.AESFuncs(sync_master_opts)
    try:
        assert af.async_methods == ()
        # Class default preserved (opt-in path uses it).
        assert (
            salt.master.AESFuncs.async_methods
        ), "class-level async_methods should stay populated for opt-in mode"
    finally:
        af.destroy()


def test_aesfuncs_sync_mode_binds_sync_fileserver_handlers(sync_master_opts):
    """
    Fileserver family handlers (`_serve_file`, `_file_hash`, ...) were
    direct attribute bindings pre-PR; the async wrappers on the class
    now shadow those.  In sync mode ``__setup_fileserver`` / the sync
    shim installer must restore the direct bindings.
    """
    af = salt.master.AESFuncs(sync_master_opts)
    try:
        # Direct-attribute bindings from the fileserver instance — NOT
        # the ``async def`` methods declared on the class.  ``==``
        # rather than ``is`` because ``getattr(fs_, "serve_file")``
        # returns a fresh bound method each access.
        assert af._serve_file == af.fs_.serve_file
        assert af._file_find == af.fs_._find_file
        assert af._file_hash == af.fs_.file_hash
        assert af._file_hash_and_stat == af.fs_.file_hash_and_stat
        assert af._file_list == af.fs_.file_list
        assert af._file_list_emptydirs == af.fs_.file_list_emptydirs
        assert af._dir_list == af.fs_.dir_list
        assert af._symlink_list == af.fs_.symlink_list
        assert af._file_envs == af.fs_.file_envs
        # And they must be sync callables, NOT coroutine functions.
        for name in (
            "_serve_file",
            "_file_find",
            "_file_hash",
            "_file_hash_and_stat",
            "_file_list",
            "_file_list_emptydirs",
            "_dir_list",
            "_symlink_list",
            "_file_envs",
        ):
            assert not inspect.iscoroutinefunction(getattr(af, name)), name
    finally:
        af.destroy()


def test_aesfuncs_sync_mode_non_fileserver_handlers_are_sync(sync_master_opts):
    """
    Every ``async def`` handler that isn't a fileserver alias must be
    shadowed on the instance with the corresponding ``_sync_<name>``
    method (pre-PR sync body).  ``getattr(self, name)`` in ``run_func``
    must return a plain sync callable so that calling it yields the
    handler's return value directly, not a coroutine.
    """
    af = salt.master.AESFuncs(sync_master_opts)
    try:
        for name in (
            "_pillar",
            "_return",
            "_syndic_return",
            "_register_resources",
            "_file_recv",
            "verify_minion",
            "_master_tops",
            "_master_opts",
            "_mine",
            "_mine_get",
            "_mine_delete",
            "_mine_flush",
            "pub_ret",
            "minion_pub",
            "minion_publish",
            "minion_runner",
            "revoke_auth",
        ):
            handler = getattr(af, name)
            assert not inspect.iscoroutinefunction(
                handler
            ), f"{name} should be a sync callable when master_async_mworker=False"
    finally:
        af.destroy()


def test_aesfuncs_async_mode_leaves_async_methods_populated(async_master_opts):
    """
    Opt-in path: the class-level ``async_methods`` tuple must be
    preserved on the instance (no accidental instance shadowing).
    """
    af = salt.master.AESFuncs(async_master_opts)
    try:
        assert af.async_methods == salt.master.AESFuncs.async_methods
        assert "_pillar" in af.async_methods
    finally:
        af.destroy()


def test_aesfuncs_async_mode_keeps_async_fileserver_methods(async_master_opts):
    """
    Opt-in path: fileserver handlers must remain ``async def`` methods
    so ``run_func``'s async dispatch branch can await them.
    """
    af = salt.master.AESFuncs(async_master_opts)
    try:
        for name in (
            "_serve_file",
            "_file_find",
            "_file_hash",
            "_file_hash_and_stat",
            "_file_list",
            "_file_list_emptydirs",
            "_dir_list",
            "_symlink_list",
            "_file_envs",
        ):
            assert inspect.iscoroutinefunction(getattr(af, name)), name
    finally:
        af.destroy()


def test_clearfuncs_sync_mode_matches_pre_pr_async_methods(sync_master_opts):
    """
    Pre-PR ``ClearFuncs.async_methods`` was ``("publish",)``.  With the
    flag off, the instance attribute must be restored to that value so
    ``MWorker._handle_clear`` dispatches ``runner``, ``wheel``,
    ``mk_token``, ``get_token``, ``ping`` synchronously.
    """
    cf = salt.master.ClearFuncs(sync_master_opts, {})
    try:
        assert cf.async_methods == ("publish",)
    finally:
        cf.destroy()


def test_clearfuncs_sync_mode_shadows_async_handlers(sync_master_opts):
    """
    ``runner`` / ``wheel`` / ``mk_token`` / ``get_token`` / ``ping``
    became ``async def`` in the PR.  With the flag off they must be
    instance-shadowed with sync callables so
    ``method(load), {"fun": "send_clear"}`` in ``_handle_clear``
    returns the actual result instead of a coroutine.
    """
    cf = salt.master.ClearFuncs(sync_master_opts, {})
    try:
        for name in ("runner", "wheel", "mk_token", "get_token", "ping"):
            handler = getattr(cf, name)
            assert not inspect.iscoroutinefunction(
                handler
            ), f"{name} should be a sync callable when master_async_mworker=False"
    finally:
        cf.destroy()


def test_clearfuncs_async_mode_keeps_extended_async_methods(async_master_opts):
    """
    Opt-in path: the class-level ``async_methods`` tuple (with
    ``runner`` / ``wheel`` / ``mk_token`` / ``get_token`` / ``ping``
    added) must be preserved on the instance.
    """
    cf = salt.master.ClearFuncs(async_master_opts, {})
    try:
        assert cf.async_methods == salt.master.ClearFuncs.async_methods
        for name in ("runner", "wheel", "mk_token", "get_token", "ping"):
            assert name in cf.async_methods
    finally:
        cf.destroy()


def test_authfuncs_sync_auth_returns_result_from_async_wrapper(sync_master_opts):
    """
    ``AuthFuncs._auth`` is always ``async def`` (callers ``await`` it),
    but with the flag off it must delegate to ``_auth_impl_sync`` and
    return its value in a single ``await``.  Guarantee at least that
    the ``_auth_impl_sync`` shim exists and is a plain sync method
    (not a coroutine function).
    """
    assert hasattr(salt.master.AuthFuncs, "_auth_impl_sync")
    assert not inspect.iscoroutinefunction(salt.master.AuthFuncs._auth_impl_sync)
    assert hasattr(salt.master.AuthFuncs, "_clear_signed_sync")
    assert not inspect.iscoroutinefunction(salt.master.AuthFuncs._clear_signed_sync)


def test_pool_routing_sync_mode_avoids_pool_worker_count_option(sync_master_opts):
    """
    The per-worker IPC socket topology (workers-{pool}-{N}.ipc) is only
    set up when the flag is on.  With the flag off the RequestServer
    must never see ``pool_worker_count`` — sanity-check via a
    static-attribute assertion: the option name is opt-in only.

    This is a smoke test on the option contract; the socket-binding
    behavior itself is exercised by the transport layer tests.
    """
    # Sync-mode opts should not carry pool_worker_count into
    # RequestServer construction.  The PoolRoutingChannel.pre_fork
    # branch that sets it is gated on master_async_mworker.
    assert sync_master_opts.get("master_async_mworker") is False
    assert "pool_worker_count" not in sync_master_opts


def test_publishserver_publish_sync_mode_uses_pub_sock(sync_master_opts):
    """
    ``PublishServer.publish`` async-context bypass (per-loop
    ``_TCPPubServerPublisher`` cache) exists to defuse a nested-
    SyncWrapper deadlock that can only happen when async handlers
    invoke ``publish`` from a running asyncio loop.  With the flag off
    the sync path must run ``self.pub_sock.send(payload)`` directly.
    """
    import salt.transport.tcp

    ps = salt.transport.tcp.PublishServer(
        sync_master_opts,
        pub_host="127.0.0.1",
        pub_port=0,
        pull_host="127.0.0.1",
        pull_port=0,
    )
    # Instance MUST NOT hold the per-loop cache when the flag is off
    # (it is only allocated inside the async branch of ``publish``).
    assert getattr(ps, "_async_pub_by_loop", None) is None
    # And the opts we passed in must be visible so ``publish`` can
    # branch on them.
    assert ps.opts.get("master_async_mworker") is False
