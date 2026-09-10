"""
Tests for salt.utils.asynchronous.SyncWrapper.

Includes regression tests for issue #65702: on Python 3.12+ the worker
thread spawned by ``SyncWrapper._wrap`` had no asyncio event loop
installed.  Any wrapped coroutine that touched
``asyncio.get_event_loop`` (notably pyzmq's future-based sockets, which
back every master-initiated job) raised
``RuntimeError: There is no current event loop in thread 'Thread-N
(_target)'`` and aborted the publish.
"""

import asyncio
import gc
import warnings

import pytest
import tornado.gen
import tornado.ioloop

import salt.utils.asynchronous as asynchronous
from tests.support.mock import patch


class HelperA:
    async_methods = [
        "sleep",
    ]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        raise tornado.gen.Return(True)


class HelperB:
    async_methods = [
        "sleep",
    ]

    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = asynchronous.SyncWrapper(HelperA)
        self.a = a

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        self.a.sleep()
        raise tornado.gen.Return(False)


class _LoopProbe:
    """
    Minimal async helper whose coroutine calls ``asyncio.get_event_loop``
    from inside the SyncWrapper worker thread - the same call pyzmq's
    ``zmq.eventloop.future`` machinery performs on every send/poll.
    """

    async_methods = ["check_loop"]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def check_loop(self):
        # On Python 3.12+ this raises RuntimeError unless an asyncio loop
        # has been installed on the current thread.  Pre-3.12 it returns
        # (and may auto-create) the loop.
        loop = asyncio.get_event_loop()
        raise tornado.gen.Return(loop is not None)


@pytest.mark.no_blocking(
    reason="HelperA.sleep yields tornado.gen.sleep(0.1); the coroutine "
    "resume callback intentionally holds the loop for 100 ms, which is "
    "exactly what the SyncWrapper contract permits and this test asserts. "
    "The asyncio slow-callback detector cannot distinguish this legitimate "
    "sync-in-async wrapping from a handler bug — see tests/pytests/unit/"
    "conftest.py::_asyncio_blocking_detection."
)
def test_helpers():
    """
    Test that the helper classes do what we expect within a regular asynchronous env
    """
    asyncio_loop = asyncio.new_event_loop()
    io_loop = tornado.ioloop.IOLoop(asyncio_loop=asyncio_loop, make_current=False)
    ret = io_loop.run_sync(lambda: HelperA().sleep())
    assert ret is True

    ret = io_loop.run_sync(lambda: HelperB().sleep())
    assert ret is False


def test_basic_wrap():
    """
    Test that we can wrap an asynchronous caller.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True


def test_basic_wrap_series():
    """
    Test that we can wrap an asynchronous caller and call the method in series.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    ret = sync.sleep()
    assert ret is True
    ret = sync.sleep()
    assert ret is True


@pytest.mark.no_blocking(
    reason="HelperB.sleep yields tornado.gen.sleep(0.1) then blocks on a "
    "SyncWrapper call — legitimate SyncWrapper stacking, not a handler "
    "bug. See test_helpers for the full rationale."
)
def test_double():
    """
    Test when the asynchronous wrapper object itself creates a wrap of another thing

    This works fine since the second wrap is based on the first's IOLoop so we
    don't have to worry about complex start/stop mechanics
    """
    sync = asynchronous.SyncWrapper(HelperB)
    ret = sync.sleep()
    assert ret is False


@pytest.mark.no_blocking(
    reason="Same SyncWrapper stacking pattern as test_double; see "
    "test_helpers for rationale."
)
def test_double_sameloop():
    """
    Test asynchronous wrappers initiated from the same IOLoop, to ensure that
    we don't wire up both to the same IOLoop (since it causes MANY problems).
    """
    a = asynchronous.SyncWrapper(HelperA)
    sync = asynchronous.SyncWrapper(HelperB, (a,))
    ret = sync.sleep()
    assert ret is False


def test_sync_wrapper_thread_has_asyncio_loop_65702():
    """
    SyncWrapper's worker thread must expose an asyncio event loop so that
    libraries which call ``asyncio.get_event_loop`` (e.g. pyzmq's
    future-based sockets used by master-initiated job publishes) work on
    Python 3.12+.
    """
    sync = asynchronous.SyncWrapper(_LoopProbe)
    try:
        assert sync.check_loop() is True
    finally:
        sync.close()


class _AsyncioTaskScheduler:
    """
    Async helper whose coroutine schedules a bare task on the asyncio
    loop that ``SyncWrapper._target`` installed as ``current`` for the
    worker thread -- mirrors what pyzmq's ``zmq.eventloop.future``
    machinery and tornado's asyncio bridge do internally when a wrapped
    coroutine touches a socket.  The scheduled task is not awaited
    from within the tornado ``run_sync``: tornado drives its own
    coroutine to completion, but any task landed on
    ``SyncWrapper.asyncio_loop`` is never iterated because that loop
    only ever has ``asyncio.set_event_loop`` called on it, never
    ``run_forever`` / ``run_until_complete``.
    """

    async_methods = ["schedule_and_return"]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def schedule_and_return(self):
        async def _child():
            # Never resolves within the outer ``run_sync`` window;
            # models a background poll / socket-read coroutine that
            # pyzmq's future-based sockets spawn and don't await
            # from inside the wrapped call.
            await asyncio.sleep(1000)
            return 1

        loop = asyncio.get_event_loop()
        loop.create_task(_child())
        raise tornado.gen.Return(True)


def test_sync_wrapper_reaps_pending_tasks_after_run_sync():
    """
    Regression test for #70169: ``SyncWrapper._target`` installs
    ``self.asyncio_loop`` as the current asyncio loop on its worker
    thread but drives the wrapped coroutine through tornado's
    ``io_loop.run_sync``.  Any ``asyncio.Task`` created inside the
    wrapped coroutine on the asyncio-side is never iterated and pins
    its coroutine + ``contextvars.Context`` until ``close()``.  Under
    long-lived driver processes (``EventReturn``, ``BatchManager``)
    that never call ``close()`` in steady state, the retention
    accumulates for the process lifetime.
    """
    # Route through ``_target`` (the cross-thread dispatch path) by
    # calling from inside a running asyncio loop -- that is the
    # ``asyncio.get_running_loop()`` branch in ``_wrap`` that spawns a
    # worker thread and calls ``asyncio.set_event_loop(asyncio_loop)``.
    sync = asynchronous.SyncWrapper(_AsyncioTaskScheduler)
    outer_loop = asyncio.new_event_loop()
    try:

        async def _driver():
            for _ in range(50):
                assert sync.schedule_and_return() is True

        outer_loop.run_until_complete(_driver())
        pending = [t for t in asyncio.all_tasks(sync.asyncio_loop) if not t.done()]
        assert not pending, (
            f"SyncWrapper leaked {len(pending)} pending asyncio Task(s) on its "
            "asyncio_loop after 50 dispatches; each pins its coroutine + "
            "contextvars.Context and is never garbage collected until close()"
        )
    finally:
        outer_loop.close()
        sync.close()


class HelperPending:
    """A helper whose wrapped coroutine leaves a task pending on the loop."""

    async_methods = [
        "start_background",
    ]

    def __init__(self, io_loop=None):
        self.io_loop = io_loop

    @tornado.gen.coroutine
    def start_background(self):
        # Leave a long-lived task behind on this wrapper's own loop, so
        # ``close()`` has something to drain.
        asyncio.ensure_future(asyncio.sleep(3600))
        raise tornado.gen.Return(True)


def test_close_drains_tasks_belonging_to_the_wrappers_own_loop():
    """
    ``close()`` runs outside the loop it is tearing down -- the calling
    thread's current loop is a different one.  ``asyncio.gather`` no longer
    takes a ``loop`` argument, so it resolves the loop from the calling
    context, and on Python 3.14 gathering tasks that belong to another loop
    raises ``ValueError: The future belongs to a different loop than the one
    specified as the loop argument``.  Earlier versions took the loop from the
    first future and let it through, so this surfaced as a wall of
    "Error during asyncio shutdown" for every proxy minion on 3.14.

    Building the gather inside the loop drains the tasks on every version.
    """
    sync = asynchronous.SyncWrapper(HelperPending)
    sync.start_background()

    pending = [t for t in asyncio.all_tasks(sync.asyncio_loop) if not t.done()]
    assert pending, "expected a task pending on the wrapper's loop"

    # The failure only happens when ``close()`` is called from inside a
    # *different running* loop, which is how it is reached in a proxy minion:
    # ``asyncio.gather`` then resolves the running loop rather than the tasks'
    # own loop and rejects them.  Drive it that way.
    #
    # Asserting on the tasks alone would not catch this either -- they are
    # cancelled before the gather, so they end up done() regardless.  The
    # symptom is the swallowed exception, so assert nothing was logged.
    async def _close_from_another_running_loop():
        with patch.object(asynchronous.log, "error") as log_error:
            sync.close()
        return log_error.call_args_list

    driver = asyncio.new_event_loop()
    try:
        errors = driver.run_until_complete(_close_from_another_running_loop())
    finally:
        driver.close()

    # Only the swallowed exception is asserted on.  The tasks themselves
    # cannot be driven to completion here -- a loop cannot be run from inside
    # another running loop -- so their state is not the thing under test.
    assert not errors, errors


def test_syncwrapper_del_safety_net_calls_close_70175():
    """
    Regression test for the __del__ safety-net cleanup extension of #70175.

    When a caller drops the last reference to a ``SyncWrapper`` without
    invoking ``close()`` or using it as a context manager, the ``__del__``
    finalizer must:

    1. Emit the ``ResourceWarning`` so the leaky caller still surfaces for
       tracking (behavior preserved from the warn-only revision).
    2. Fall back to ``close()`` so the wrapped ``obj`` is released and the
       owned ``asyncio.new_event_loop()`` is actually closed -- otherwise
       every abandoned wrapper leaks a whole IOLoop + ZMQ context +
       socketpairs, which is the observed ~50 MB/hr RSS growth on the
       minion.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    asyncio_loop = sync.asyncio_loop
    assert not asyncio_loop.is_closed()
    assert sync.obj is not None

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        del sync
        gc.collect()

    # 1. ResourceWarning still fires.
    resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert resource_warnings, (
        "expected ResourceWarning from SyncWrapper.__del__; got "
        f"{[(w.category, str(w.message)) for w in caught]}"
    )
    assert any("unclosed SyncWrapper" in str(w.message) for w in resource_warnings)

    # 2. Safety-net close() ran: the underlying asyncio loop is now closed.
    #    Without the safety-net, ``asyncio_loop.is_closed()`` stays False
    #    forever because nothing else has a handle on it -- it leaks as a
    #    dangling loop object with its selector, kqueue/epoll fd, and any
    #    tornado bridging state.  ``close()`` is the only place that drives
    #    ``self.asyncio_loop.close()``.
    assert (
        asyncio_loop.is_closed()
    ), "SyncWrapper.__del__ safety-net did not drive asyncio_loop.close()"


def test_syncwrapper_del_forked_child_does_not_touch_parent_resources_70175(
    monkeypatch,
):
    """
    Regression test for fork-safety of the __del__ safety-net cleanup.

    Reproduces the failure mode observed in
    tests/pytests/unit/utils/event/test_event.py::test_event_no_timeout:
    ``EventSender`` forks a child process which inherits the parent's
    ``MasterEvent`` -> ``SyncWrapper`` -> ``ipc_publish_client`` (which
    wraps a real socket FD).  When the child exits, GC calls the
    inherited wrapper's ``__del__``; without the ``_creator_pid`` guard,
    that ``__del__`` fires ``close()`` on the shared socket FD, breaking
    the parent's transport (``recv()`` in the parent then blocks forever
    waiting on an event bus with no live connection).

    Guard contract:

    - ``__init__`` records ``self._creator_pid = os.getpid()``.
    - ``__del__`` short-circuits (no warn, no close) when
      ``os.getpid() != self._creator_pid`` -- the parent still owns the
      wrapped ``obj`` / io_loop / asyncio_loop; the child must NOT
      ``close()`` them.
    """
    sync = asynchronous.SyncWrapper(HelperA)
    asyncio_loop = sync.asyncio_loop
    creator_pid = sync._creator_pid
    assert creator_pid > 0
    assert not asyncio_loop.is_closed()

    # Simulate ``os.getpid()`` returning a different pid, as it would in
    # a forked child.  Do NOT actually fork -- the parent's ``sync``
    # reference has to survive so we can assert on it after GC.
    monkeypatch.setattr("salt.utils.asynchronous.os.getpid", lambda: creator_pid + 1)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        del sync
        gc.collect()

    # 1. No ResourceWarning: the wrapper is not "our" object in the child.
    resource_warnings = [w for w in caught if issubclass(w.category, ResourceWarning)]
    unclosed_syncwrapper = [
        w for w in resource_warnings if "unclosed SyncWrapper" in str(w.message)
    ]
    assert not unclosed_syncwrapper, (
        "forked-child SyncWrapper.__del__ must NOT emit 'unclosed SyncWrapper' warning "
        f"(fork-safety guard broken): {[str(w.message) for w in unclosed_syncwrapper]}"
    )

    # 2. Safety-net close() did NOT run in the "child": the underlying
    #    asyncio_loop is still open (the parent still owns it).  Without
    #    the guard, ``__del__`` would drive ``asyncio_loop.close()``.
    assert not asyncio_loop.is_closed(), (
        "forked-child SyncWrapper.__del__ must NOT close the shared asyncio_loop "
        "(fork-safety guard broken -- parent's transport would be destroyed)"
    )
