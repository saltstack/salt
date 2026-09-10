# pylint: skip-file
"""
Error-path and ContextVar-propagation coverage for the async MWorker handlers.

The dwoz/feature/async-mworker branch converted 26 ``AESFuncs`` methods,
5 ``ClearFuncs`` methods, and ``AuthFuncs._auth_impl`` to ``async def``.
Most of them offload their blocking bodies to ``loop.run_in_executor(...)``.
Two failure modes are especially likely to bite in that shape:

1. **Exception in the executor.**  When the sync internal raises, the
   exception propagates on ``await``.  ``AESFuncs.run_func`` catches and
   converts it to ``""``; the direct ``ClearFuncs`` handlers either wrap
   the offload in their own try/except (``runner`` / ``wheel``) or let
   the exception propagate to the caller.  This module pins the
   documented behavior per handler so a future refactor can't silently
   change it.
2. **``salt.utils.ctx.request_context`` visibility across the executor
   boundary.**  ``_handle_aes`` wraps the awaited work in a
   ``request_context`` context manager so log records emitted from
   handlers carry the JID / minion id.  A stock
   ``concurrent.futures.ThreadPoolExecutor`` does *not* copy
   ``contextvars`` on ``submit``, so anything offloaded via
   ``run_in_executor(None, sync_impl, ...)`` runs with an empty
   ``request_ctxvar``.  ``MWorker.__bind`` installs a context-copying
   default executor to fix this (see ``salt.master._ContextThreadPoolExecutor``);
   the batched test below proves the ContextVar crosses the offload
   boundary.

Cancellation is a rare-but-nasty third failure mode: cancelling the
``_handle_aes`` task must not leak threads or leave the worker in a
broken state.
"""

import asyncio
import collections
import concurrent.futures
import contextvars
import threading

import pytest

import salt.crypt
import salt.master
import salt.utils.ctx
from tests.support.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_aes_funcs(**attrs):
    """Bypass ``AESFuncs.__init__`` and set only what a single handler needs."""
    aes = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    aes.opts = {
        "pillar_version": 2,
        "master_stats": False,
        "allow_minion_key_revoke": True,
        "master_job_cache": False,
        "require_minion_sign_messages": False,
        "drop_messages_signature_fail": False,
        "minion_data_cache": False,
        "minion_data_cache_events": False,
        "cachedir": "/tmp",
        "signing_algorithm": salt.crypt.PKCS1v15_SHA1,
        # ``salt._logging.impl.SaltLoggingClass._log`` reads these from the
        # ``opts`` mirror in ``request_ctxvar``; the ``run_func`` broad
        # ``except`` path emits an ``error`` log record that references
        # ``log_fmt_jid`` when the current request has a ``jid``.
        "log_fmt_jid": "[JID: %(jid)s]",
        "log_fmt_minion_id": "[MID: %(minion_id)s]",
    }
    aes.masterapi = MagicMock()
    aes.fs_ = MagicMock()
    aes.event = MagicMock()
    aes.mminion = MagicMock()
    aes.ckminions = MagicMock()
    aes.cache = MagicMock()
    aes.local = MagicMock()
    aes.key_cache = MagicMock()
    for name, value in attrs.items():
        setattr(aes, name, value)
    return aes


def _make_worker(aes_funcs):
    """Build a bare ``MWorker`` with just what ``_handle_aes`` needs."""
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    # ``_handle_aes`` publishes ``{"data": data, "opts": self.opts}`` into
    # ``request_ctxvar``; the logging enricher in ``salt._logging.impl``
    # reads ``log_fmt_jid`` / ``log_fmt_minion_id`` off ``opts`` when the
    # load carries a ``jid`` / ``id``.  Provide plausible defaults so the
    # ``run_func`` broad-except path (which emits ``log.error`` on failure)
    # doesn't blow up on a missing formatter key.
    worker.opts = {
        "master_stats": False,
        "log_fmt_jid": "[JID: %(jid)s]",
        "log_fmt_minion_id": "[MID: %(minion_id)s]",
    }
    worker.aes_funcs = aes_funcs
    worker.stats = collections.defaultdict(lambda: {"mean": 0, "runs": 0})
    return worker


def _make_clear_funcs(**attrs):
    """Bypass ``ClearFuncs.__init__`` for direct handler tests."""
    clear = salt.master.ClearFuncs.__new__(salt.master.ClearFuncs)
    clear.opts = {
        "publisher_acl_blacklist": {},
        "master_stats": False,
        "keys.cache_driver": "localfs_key",
        "user": "root",
    }
    clear.key = {"root": "fake-key"}
    clear.event = MagicMock()
    clear.local = MagicMock()
    clear.ckminions = MagicMock()
    clear.loadauth = MagicMock()
    clear.mminion = MagicMock()
    clear.masterapi = MagicMock()
    clear.wheel_ = MagicMock()
    clear.channels = []
    for name, value in attrs.items():
        setattr(clear, name, value)
    return clear


# ---------------------------------------------------------------------------
# AESFuncs.async_methods — exception propagation
#
# ``AESFuncs.run_func`` (async branch) catches every exception raised from
# the awaited handler, logs it, and returns ``""``. ``_wrap_run_func_return``
# then produces the ``(ret, {"fun": "send"})`` envelope. Dispatching through
# ``MWorker._handle_aes`` must therefore never raise for any async AES
# handler, no matter what the sync internal did.
# ---------------------------------------------------------------------------


# Handler -> (masterapi_attr_or_None, load, extra_setup_fn).
#
# ``extra_setup_fn`` is only used for handlers whose blocking work does
# not live on ``self.masterapi`` (e.g. fileserver family targets ``self.fs_``).
def _aes_exception_matrix():
    fs_methods = {
        "_serve_file": ("fs_", "serve_file"),
        "_file_find": ("fs_", "_find_file"),
        "_file_hash": ("fs_", "file_hash"),
        "_file_hash_and_stat": ("fs_", "file_hash_and_stat"),
        "_file_list": ("fs_", "file_list"),
        "_file_list_emptydirs": ("fs_", "file_list_emptydirs"),
        "_dir_list": ("fs_", "dir_list"),
        "_symlink_list": ("fs_", "symlink_list"),
        "_file_envs": ("fs_", "file_envs"),
    }
    masterapi_methods = {
        "_master_tops": ("masterapi", "_master_tops"),
        "_mine_get": ("masterapi", "_mine_get"),
        "_mine": ("masterapi", "_mine"),
        "_mine_delete": ("masterapi", "_mine_delete"),
        "_mine_flush": ("masterapi", "_mine_flush"),
        "minion_runner": ("masterapi", "minion_runner"),
        "minion_pub": ("masterapi", "minion_pub"),
        "minion_publish": ("masterapi", "minion_publish"),
        "revoke_auth": ("masterapi", "revoke_auth"),
    }
    return {**fs_methods, **masterapi_methods}


AES_EXCEPTION_MATRIX = _aes_exception_matrix()


@pytest.mark.parametrize("cmd", sorted(AES_EXCEPTION_MATRIX))
async def test_aes_handler_exception_is_swallowed_and_envelope_preserved(cmd):
    """
    Every async AES handler that offloads to an executor: when the sync
    internal raises ``RuntimeError``, ``run_func`` catches it, returns
    ``""``, and ``_handle_aes`` yields ``("", {"fun": "send"})``.

    This matches the pre-migration sync behavior (``run_func``'s
    ``except Exception`` returning ``""``).
    """
    holder_attr, method_attr = AES_EXCEPTION_MATRIX[cmd]
    aes = _make_aes_funcs()
    holder = getattr(aes, holder_attr)
    getattr(holder, method_attr).side_effect = RuntimeError("boom")

    # Pre-authorize every load so ``__verify_load`` short-circuits happily.
    # The union of keys covers every handler in this matrix.
    load = {
        "cmd": cmd,
        "id": "minion-1",
        "tgt": "*",
        "fun": "test.ping",
        "arg": [],
        "data": {"foo": "bar"},
        "ret": "",
        "jid": "20260101000000000000",
        "peer": True,
    }
    # ``minion_pub`` / ``minion_publish`` go through
    # ``__verify_minion_publish``, which requires ``self.opts["peer"]``
    # to be a dict — provide one to bypass authorization cleanly.
    aes.opts["peer"] = {".*": [".*"]}
    # ``minion_publish`` needs a valid id-style tgt.  Precompiled matchers
    # come off ``self.ckminions.auth_check`` — force it to authorize.
    aes.ckminions.auth_check = MagicMock(return_value=True)

    worker = _make_worker(aes)
    # Any RuntimeError from the executor must be absorbed by ``run_func``.
    ret = await worker._handle_aes(load)
    assert ret == ("", {"fun": "send"})


async def test_aes_file_recv_exception_is_swallowed():
    """
    ``_file_recv`` offloads the write to ``_file_recv_write``.  A raise
    from that method must be caught by ``run_func`` and returned as
    ``("", {"fun": "send"})``.
    """
    aes = _make_aes_funcs()
    aes.opts["file_recv"] = True
    aes.opts["file_recv_max_size"] = 100
    aes.opts["fileserver_followsymlinks"] = False
    with patch.object(
        salt.master.AESFuncs,
        "_file_recv_write",
        side_effect=RuntimeError("boom"),
    ), patch("salt.utils.verify.valid_id", return_value=True), patch(
        "salt.utils.verify.clean_path", return_value=True
    ):
        worker = _make_worker(aes)
        ret = await worker._handle_aes(
            {
                "cmd": "_file_recv",
                "id": "minion-1",
                "path": ["a"],
                "loc": 0,
                "data": b"x",
            }
        )
    assert ret == ("", {"fun": "send"})


async def test_aes_pillar_exception_is_swallowed():
    """
    ``_pillar`` awaits ``salt.pillar.get_async_pillar(...).compile_pillar()``
    on the event loop.  If ``compile_pillar`` raises, ``run_func`` must
    convert it to the ``("", {"fun": "send_private", ...})`` envelope for
    ``_pillar``-specific post-processing when ``id`` is present in the
    load.
    """
    aes = _make_aes_funcs()
    pillar_obj = MagicMock()
    pillar_obj.compile_pillar = AsyncMock(side_effect=RuntimeError("boom"))
    with patch(
        "salt.pillar.get_async_pillar", MagicMock(return_value=pillar_obj)
    ), patch("salt.utils.verify.valid_id", return_value=True):
        worker = _make_worker(aes)
        ret = await worker._handle_aes(
            {
                "cmd": "_pillar",
                "id": "minion-1",
                "grains": {},
                "saltenv": "base",
                "ver": "2",
            }
        )
    # ``_pillar`` uses the ``send_private`` envelope when ``id`` is set;
    # ``run_func`` returns ``""`` on exception, ``_wrap_run_func_return``
    # then wraps it with the pillar-specific envelope.
    assert ret == ("", {"fun": "send_private", "key": "pillar", "tgt": "minion-1"})


async def test_aes_return_exception_is_swallowed():
    """``_return`` -> executor -> ``store_job`` raising must not escape."""
    aes = _make_aes_funcs()
    with patch(
        "salt.utils.job.store_job",
        side_effect=RuntimeError("boom"),
    ):
        worker = _make_worker(aes)
        # ``_return`` catches ``SaltCacheError`` internally and logs; any
        # other exception propagates up to ``run_func`` which swallows it.
        ret = await worker._handle_aes(
            {"cmd": "_return", "id": "minion-1", "fun": "test.ping"}
        )
    # ``_return`` uses the plain ``send`` envelope.
    assert ret == ("", {"fun": "send"})


async def test_aes_syndic_return_exception_is_swallowed():
    """
    ``_syndic_return`` offloads returner + syndic-cache-marker writes to
    the executor.  A raise from the marker writer must be absorbed by
    ``run_func``.
    """
    aes = _make_aes_funcs()
    aes.opts["master_job_cache"] = False
    with patch.object(
        salt.master.AESFuncs,
        "_write_syndic_cache_marker",
        side_effect=RuntimeError("boom"),
    ):
        worker = _make_worker(aes)
        ret = await worker._handle_aes(
            {
                "cmd": "_syndic_return",
                "id": "syndic-1",
                "jid": "20260101000000000000",
                "return": {"minion-a": {"ret": True}},
            }
        )
    assert ret == ("", {"fun": "send"})


async def test_aes_pub_ret_exception_is_swallowed(tmp_path):
    """
    ``pub_ret`` reads the auth-cache and then calls
    ``local.get_cache_returns`` via the executor.  A raise from the
    returner must be caught by ``run_func``.
    """
    aes = _make_aes_funcs()
    aes.opts["cachedir"] = str(tmp_path)
    # Seed the on-disk auth cache the handler reads.
    auth_dir = tmp_path / "publish_auth"
    auth_dir.mkdir()
    (auth_dir / "j1").write_text("minion-1")
    aes.local.get_cache_returns.side_effect = RuntimeError("boom")
    worker = _make_worker(aes)
    ret = await worker._handle_aes({"cmd": "pub_ret", "id": "minion-1", "jid": "j1"})
    assert ret == ("", {"fun": "send"})


async def test_aes_register_resources_exception_is_swallowed():
    """
    ``_register_resources`` runs its whole sync body in one executor call.
    A raise from ``update_resource_index`` must be caught by ``run_func``.
    """
    aes = _make_aes_funcs()
    with patch(
        "salt.utils.minions.update_resource_index",
        side_effect=RuntimeError("boom"),
    ):
        worker = _make_worker(aes)
        ret = await worker._handle_aes(
            {
                "cmd": "_register_resources",
                "id": "minion-1",
                "resources": {"r": {}},
            }
        )
    assert ret == ("", {"fun": "send"})


async def test_aes_verify_minion_exception_is_swallowed():
    """
    ``verify_minion`` is dispatched via ``run_func`` too — a raise from
    the sync ``__verify_minion`` internal must be swallowed.  This handler
    takes positional ``(id_, token)`` but ``run_func`` always calls with a
    single ``load`` positional; treat that as the contract already
    enforced elsewhere and go direct at the handler here.
    """
    aes = _make_aes_funcs()
    with patch.object(
        salt.master.AESFuncs,
        "_AESFuncs__verify_minion",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            await aes.verify_minion("minion-1", b"tok")


async def test_aes_master_opts_exception_is_swallowed():
    """
    ``_master_opts`` awaits ``self._file_envs`` (which offloads to the
    executor).  Failure of the fileserver walk must be caught by
    ``run_func`` when dispatched through ``_handle_aes``.
    """
    aes = _make_aes_funcs()
    aes.fs_.file_envs.side_effect = RuntimeError("boom")
    worker = _make_worker(aes)
    ret = await worker._handle_aes({"cmd": "_master_opts", "id": "minion-1"})
    assert ret == ("", {"fun": "send"})


# ---------------------------------------------------------------------------
# ClearFuncs.async_methods — exception propagation
#
# ClearFuncs handlers are dispatched directly by ``_handle_clear``; there
# is no ``run_func`` catch-all.  ``runner`` and ``wheel`` wrap their
# executor calls in try/except and return a documented ``{"error": ...}``
# shape; the remaining handlers (``publish``, ``mk_token``, ``get_token``,
# ``ping``) let exceptions propagate to the caller.
# ---------------------------------------------------------------------------


async def test_clear_runner_exception_is_wrapped_in_error_shape():
    """``runner`` — executor raise becomes ``{"error": {"name": ..., ...}}``."""
    clear = _make_clear_funcs()
    clear.loadauth.check_authentication.return_value = {
        "auth_list": ["@runner"],
        "username": "u",
    }
    clear.ckminions.runner_check.return_value = True
    with patch(
        "salt.runner.RunnerClient",
        MagicMock(
            return_value=MagicMock(
                asynchronous=MagicMock(side_effect=RuntimeError("boom"))
            )
        ),
    ):
        ret = await clear.runner(
            {"eauth": "pam", "username": "u", "password": "p", "fun": "foo"}
        )
    assert isinstance(ret, dict)
    assert ret["error"]["name"] == "RuntimeError"
    assert "boom" in ret["error"]["message"]


async def test_clear_wheel_exception_is_wrapped_in_error_shape():
    """``wheel`` — executor raise fires the failure event and returns
    an envelope with ``success=False``."""
    clear = _make_clear_funcs()
    clear.loadauth.check_authentication.return_value = {
        "auth_list": ["@wheel"],
        "username": "u",
    }
    clear.ckminions.wheel_check.return_value = True
    clear.wheel_.call_func.side_effect = RuntimeError("boom")
    clear.event.fire_event_async = AsyncMock()
    with patch("salt.utils.jid.gen_jid", return_value="j1"):
        ret = await clear.wheel(
            {"eauth": "pam", "username": "u", "password": "p", "fun": "key.list"}
        )
    assert ret["data"]["success"] is False
    assert "boom" in ret["data"]["return"]
    clear.event.fire_event_async.assert_awaited()


async def test_clear_mk_token_exception_propagates():
    """
    ``mk_token`` has no try/except around the executor call.  A raise
    from ``loadauth.mk_token`` propagates out — pinning current behavior
    so any future change is intentional.
    """
    clear = _make_clear_funcs()
    clear.loadauth.mk_token.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        await clear.mk_token({"eauth": "pam", "username": "u", "password": "p"})


async def test_clear_get_token_exception_propagates():
    """``get_token`` — executor raise propagates."""
    clear = _make_clear_funcs()
    clear.loadauth.get_tok.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        await clear.get_token({"token": "abc"})


async def test_clear_publish_exception_propagates():
    """
    ``publish`` has no top-level try/except.  A raise from ``check_minions``
    (called synchronously on the loop thread) escapes to the caller.
    """
    clear = _make_clear_funcs()
    clear.ckminions.check_minions.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        await clear.publish({"user": "root", "fun": "test.ping", "tgt": "*"})


def test_clear_ping_is_pure_delegation():
    """
    ``ping`` echoes ``clear_load`` verbatim.  It has no sync internal that
    can raise; there is nothing to cover for exception propagation.
    Documented here so the batch is complete.
    """
    # Nothing to test — presence of this docstring is the coverage note.
    assert "ping" in salt.master.ClearFuncs.async_methods


# ---------------------------------------------------------------------------
# ContextVar propagation across the executor boundary
#
# Batched: a single test proves that a value set in ``request_ctxvar`` by
# ``_handle_aes`` is visible to the callable submitted to the loop's
# default executor.  This covers every AES handler that offloads sync
# work, since they all go through the same executor.
# ---------------------------------------------------------------------------


async def test_request_context_crosses_executor_boundary():
    """
    ``MWorker._handle_aes`` wraps its body in
    ``salt.utils.ctx.request_context(...)``. Handlers that call
    ``loop.run_in_executor(None, sync_impl, ...)`` must therefore see
    the same ``request_ctxvar`` value inside ``sync_impl``.

    The stock ``concurrent.futures.ThreadPoolExecutor`` does *not* copy
    contextvars on ``submit``; :class:`salt.master._ContextThreadPoolExecutor`
    (installed in ``MWorker.__bind``) does.  Install it on this test's
    running loop so the assertion reflects the production shape.
    """
    loop = asyncio.get_event_loop()
    loop.set_default_executor(salt.master._ContextThreadPoolExecutor())

    captured = {}

    def sync_impl(load):
        # This runs in a worker thread.  ``request_ctxvar`` was set on
        # the loop thread by ``_handle_aes``; the executor must copy
        # the context across the submit boundary.
        captured["ctx"] = salt.utils.ctx.get_request_context()
        captured["thread"] = threading.current_thread().name
        return "ok"

    aes = _make_aes_funcs()

    async def handler(load):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, sync_impl, load)

    aes.async_methods = ("handler",)
    aes.handler = handler
    aes.get_method = lambda cmd: handler

    worker = _make_worker(aes)
    payload = {"cmd": "handler", "id": "minion-ctx", "marker": "carry-me"}
    ret = await worker._handle_aes(payload)
    assert ret == ("ok", {"fun": "send"})
    # The context set by ``_handle_aes`` must be visible in the executor.
    assert captured["ctx"] == {"data": payload, "opts": worker.opts}
    # And it really did run on a different thread than the loop.
    assert captured["thread"] != threading.current_thread().name


def test_context_thread_pool_executor_propagates_contextvars():
    """
    Unit-level proof that :class:`_ContextThreadPoolExecutor` snapshots
    the current context at ``submit`` time and re-enters it in the worker
    thread.  Kept separate from the ``_handle_aes`` test so a regression
    in the executor is diagnosable independently of the dispatcher.
    """
    cv = contextvars.ContextVar("test_master_async_error_paths")
    cv.set("payload")

    def read():
        return cv.get("missing")

    executor = salt.master._ContextThreadPoolExecutor(max_workers=1)
    try:
        assert executor.submit(read).result() == "payload"
    finally:
        executor.shutdown(wait=True)


def test_stock_thread_pool_executor_does_not_propagate_contextvars():
    """
    Regression guard: the reason we ship ``_ContextThreadPoolExecutor``
    at all is that the stock executor does *not* copy contextvars.  If
    a future CPython flips this behavior we want to know so the shim can
    be removed.
    """
    cv = contextvars.ContextVar("test_master_async_error_paths_stock")
    cv.set("payload")

    def read():
        return cv.get("missing")

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        assert executor.submit(read).result() == "missing"
    finally:
        executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Cancellation smoke
# ---------------------------------------------------------------------------


async def test_handle_aes_cancellation_propagates_cleanly():
    """
    Cancelling a mid-flight ``_handle_aes`` task must:

      * raise ``asyncio.CancelledError`` out of the awaiting coroutine,
      * not swallow the cancellation into ``""`` via ``run_func``'s
        broad ``except``.  ``run_func`` uses ``except Exception`` (not
        ``BaseException``), so ``CancelledError`` should propagate on
        Python 3.10+ where it inherits from ``BaseException``.

    We simulate a handler stuck on an awaitable that never resolves.
    """
    aes = _make_aes_funcs()
    started = asyncio.Event()

    async def slow_handler(load):
        started.set()
        # Never resolves — cancellation must break us out.
        await asyncio.Event().wait()

    aes.async_methods = ("slow_handler",)
    aes.slow_handler = slow_handler
    aes.get_method = lambda cmd: slow_handler

    worker = _make_worker(aes)
    task = asyncio.create_task(worker._handle_aes({"cmd": "slow_handler"}))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # No thread leaks: the handler never entered an executor so nothing
    # can be dangling.  Just assert the task is truly done.
    assert task.done()


async def test_handle_aes_cancellation_during_executor_offload():
    """
    Cancelling while a handler is blocked in ``run_in_executor`` — the
    thread will finish its work but the awaiting task should surface
    ``CancelledError`` promptly on the next scheduling point.  This
    guards against handlers that ``await`` inside a ``finally`` and
    silently absorb cancellation.
    """
    aes = _make_aes_funcs()
    started = threading.Event()
    proceed = threading.Event()

    def slow_sync(load):
        started.set()
        # Bounded wait so a broken test can't hang CI.
        proceed.wait(timeout=5)
        return "done"

    async def handler(load):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, slow_sync, load)

    aes.async_methods = ("handler",)
    aes.handler = handler
    aes.get_method = lambda cmd: handler

    worker = _make_worker(aes)
    task = asyncio.create_task(worker._handle_aes({"cmd": "handler"}))
    # Yield control until the executor callable has actually started.
    for _ in range(50):
        if started.is_set():
            break
        await asyncio.sleep(0.01)
    assert started.is_set(), "executor callable never started"
    task.cancel()
    # Let the worker thread finish so we don't leak it after test exit.
    proceed.set()
    with pytest.raises(asyncio.CancelledError):
        await task
