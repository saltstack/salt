"""
Unit tests for the ``SaltEvent.fire_event`` async-context handling
added for #69986.

The fix removes ``publish`` from ``PublishServer.async_methods`` (and
``send`` / ``connect`` / ``_connect`` from
``_TCPPubServerPublisher.async_methods``) so ``SyncWrapper`` exposes
the raw async coroutine methods rather than the wedging sync
``_wrap`` form.  ``SaltEvent.fire_event`` (a sync method) then
detects the coroutine return value and either schedules it on the
running loop (async context) or drives it through the SyncWrapper's
owned ``io_loop.run_sync`` (sync context).

These are unit-scale checks with no sockets or subprocess; the
functional repro that catches the actual production deadlock lives at
``tests/pytests/functional/transport/tcp/test_deadlock_repro.py``.
"""

import asyncio

import pytest

import salt.transport.tcp
import salt.utils.event


def test_publish_server_publish_not_in_async_methods():
    """
    Regression for #69986: ``publish`` must NOT be in
    ``PublishServer.async_methods``.  Adding it back would put the
    ``SyncWrapper._wrap`` sync form (which does ``thread.join()``
    inside async callers) between callers and the coroutine.
    """
    assert "publish" not in salt.transport.tcp.PublishServer.async_methods, (
        "PublishServer.async_methods must not contain 'publish' -- see "
        "#69986; the sync _wrap form wedges the caller's asyncio loop."
    )


def test_publish_server_has_async_pubs_cache():
    """
    ``PublishServer`` must carry a per-loop ``_async_pubs``
    WeakKeyDictionary so ``publish`` on a running loop can use a raw
    ``_TCPPubServerPublisher`` bound to that loop, rather than the
    SyncWrapper-based ``self.pub_sock`` whose IOStream is tied to a
    different loop (loop-mismatch hang, #69986).
    """
    import weakref

    inst = salt.transport.tcp.PublishServer(
        {}, pub_host="127.0.0.1", pub_port=0, pull_host="127.0.0.1", pull_port=0
    )
    try:
        assert isinstance(inst._async_pubs, weakref.WeakKeyDictionary)
    finally:
        inst.close()


class FakeCoroPusher:
    """
    Stand-in for a raw ``PublishServer`` (post-fix): ``publish``
    returns a real coroutine so ``fire_event`` exercises its
    ``iscoroutine`` handling branch.
    """

    def __init__(self):
        self.published = []
        self.io_loop = None  # not used on the async-context path

    async def publish(self, msg, **_kw):
        self.published.append((msg, asyncio.get_running_loop()))

    def close(self):
        pass


@pytest.fixture
def event_opts(tmp_path):
    return {
        "id": "test-master",
        "sock_dir": str(tmp_path),
        "transport": "tcp",
        "ipc_mode": "tcp",
        "publish_signing_algorithm": "PKCS1v15-SHA1",
        "max_event_size": 1048576,
    }


def _new_event(event_opts, tmp_path):
    return salt.utils.event.SaltEvent(
        "master",
        sock_dir=str(tmp_path),
        opts=event_opts,
        listen=False,
    )


def test_fire_event_async_context_schedules_coroutine_on_running_loop(
    event_opts, tmp_path
):
    """
    When ``pusher.publish`` returns a coroutine and ``fire_event`` is
    called from a running loop, ``fire_event`` must schedule the
    coroutine on THAT loop (not the wedging SyncWrapper thread+join).
    """
    event = _new_event(event_opts, tmp_path)
    fake_pusher = FakeCoroPusher()
    event.pusher = fake_pusher
    event.cpush = True

    async def _run():
        loop = asyncio.get_running_loop()
        ret = event.fire_event({"payload": "async"}, tag="unit/async")
        # Give the scheduled task a chance to run.
        for _ in range(3):
            await asyncio.sleep(0)
        return ret, loop

    try:
        ret, loop = asyncio.run(_run())
        assert ret is True
        assert len(fake_pusher.published) == 1
        _, task_loop = fake_pusher.published[0]
        assert task_loop is loop, (
            "coroutine must run on the caller's running loop, not on a "
            "SyncWrapper's owned loop."
        )
    finally:
        event.destroy()


def test_fire_event_async_context_does_not_block_caller(event_opts, tmp_path):
    """
    ``fire_event`` from async context is fire-and-forget: the sync
    method must return immediately even if the underlying coroutine
    never resolves.  If it accidentally ``await``-blocked (via any
    hidden ``thread.join``), this test would hang.
    """

    class NeverResolvingPusher:
        io_loop = None

        async def publish(self, msg, **_kw):
            await asyncio.Event().wait()  # never completes

        def close(self):
            pass

    event = _new_event(event_opts, tmp_path)
    event.pusher = NeverResolvingPusher()
    event.cpush = True

    async def _run():
        ret = event.fire_event({"payload": "nowait"}, tag="unit/nowait")
        # Don't yield -- prove fire_event returned synchronously.
        return ret

    try:
        assert asyncio.run(_run()) is True
    finally:
        event.destroy()


def test_fire_event_sync_context_drives_coroutine_via_pusher_loop(event_opts, tmp_path):
    """
    When called with no running loop, ``fire_event`` must drive the
    returned coroutine via the SyncWrapper's owned ``io_loop.run_sync``
    so the send actually completes (not silently dropped).
    """
    driven = {"called": False}

    class SyncPusher:
        published = []

        class _FakeIOLoop:
            @staticmethod
            def run_sync(fn):
                # Consume the coroutine returned by fn so we exercise
                # the sync-context branch without a real Tornado loop.
                driven["called"] = True
                coro = fn()
                try:
                    coro.send(None)
                except StopIteration:
                    pass
                except Exception:  # pylint: disable=broad-except
                    pass
                return None

        io_loop = _FakeIOLoop()

        async def publish(self, msg, **_kw):
            SyncPusher.published.append(msg)

        def close(self):
            pass

    event = _new_event(event_opts, tmp_path)
    event.pusher = SyncPusher()
    event.cpush = True

    try:
        assert event.fire_event({"payload": "sync"}, tag="unit/sync") is True
        assert driven["called"] is True
        assert len(SyncPusher.published) == 1
    finally:
        event.destroy()
