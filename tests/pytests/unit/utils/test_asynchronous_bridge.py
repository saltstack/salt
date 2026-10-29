"""Lifecycle and concurrency tests for the synchronous asyncio bridge."""

import asyncio
import concurrent.futures
import contextvars
import gc
import multiprocessing
import multiprocessing.util
import os
import sys
import threading
import warnings

import pytest

import salt.utils.asynchronous as asyncbridge

pytestmark = [pytest.mark.timeout(20)]


@pytest.fixture
def bridge():
    instance = asyncbridge.LoopBridge()
    try:
        yield instance
    finally:
        instance.shutdown()


@pytest.fixture
def shared_bridge(monkeypatch):
    monkeypatch.setattr(asyncbridge, "_bridge", None)
    monkeypatch.setattr(asyncbridge, "_bridge_lock", threading.Lock())
    monkeypatch.setattr(asyncbridge, "_bridge_shutdown", False)
    monkeypatch.setattr(asyncbridge, "_bridge_finalizer", None)
    try:
        yield
    finally:
        asyncbridge.shutdown_bridge()


async def _answer():
    return 42


def test_result_and_exception_are_propagated(bridge):
    async def fail():
        raise ValueError("request failed")

    assert bridge.run(_answer()) == 42
    with pytest.raises(ValueError, match="request failed"):
        bridge.run(fail())
    assert bridge.run(_answer()) == 42


def test_coroutine_timeout_exception_is_preserved(bridge):
    error = concurrent.futures.TimeoutError("transport timeout")

    async def fail():
        raise error

    with pytest.raises(concurrent.futures.TimeoutError) as exc:
        bridge.run(fail())
    assert exc.value is error


def test_concurrent_callers_share_the_same_loop_and_thread(bridge):
    async def identify():
        await asyncio.sleep(0)
        return id(asyncio.get_running_loop()), threading.get_ident()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(bridge.run, identify()) for _ in range(100)]
        results = [future.result(5) for future in futures]
    assert set(results) == {(id(bridge._loop), bridge._thread.ident)}
    assert bridge._thread.ident != threading.get_ident()


def test_call_context_is_copied_and_changes_do_not_leak(bridge):
    value = contextvars.ContextVar("bridge_test_context", default="default")

    async def read_and_change():
        result = value.get()
        await asyncio.sleep(0)
        value.set("changed in task")
        return result

    def call(number):
        value.set(number)
        result = bridge.run(read_and_change())
        assert value.get() == number
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(call, number) for number in range(20)]
        assert [future.result(5) for future in futures] == list(range(20))
    assert bridge.run(read_and_change()) == "default"


def test_timeout_cancels_only_its_call(bridge):
    started = threading.Event()
    cleaned = threading.Event()

    async def wait():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    async def create_survivor():
        return asyncio.create_task(asyncio.Event().wait())

    survivor = bridge.run(create_survivor())
    with pytest.raises(TimeoutError):
        bridge.run(wait(), timeout=0.1)
    assert started.is_set()
    assert cleaned.wait(5)

    async def check_survivor():
        return survivor.done()

    assert bridge.run(check_survivor()) is False
    assert bridge.run(_answer()) == 42


@pytest.mark.no_blocking(
    reason="Hold the loop to test cancellation before submission runs"
)
def test_cancellation_before_task_creation_closes_the_coroutine(bridge):
    entered = threading.Event()
    release = threading.Event()

    def hold_loop():
        entered.set()
        release.wait(5)

    bridge._loop.call_soon_threadsafe(hold_loop)
    assert entered.wait(5)
    coro = _answer()
    try:
        with pytest.raises(TimeoutError):
            bridge.run(coro, timeout=0)
    finally:
        release.set()
    # This call is queued after the cancelled submission and its cleanup.
    assert bridge.run(_answer(), timeout=5) == 42
    assert coro.cr_frame is None


@pytest.mark.parametrize("timeout", [-1, float("inf"), float("nan")])
def test_invalid_call_timeout_closes_the_coroutine(bridge, timeout):
    coro = _answer()
    with pytest.raises(ValueError, match="finite and non-negative"):
        bridge.run(coro, timeout=timeout)
    assert coro.cr_frame is None


def test_future_or_regular_value_is_rejected(bridge):
    with pytest.raises(TypeError, match="requires a coroutine"):
        bridge.run(concurrent.futures.Future())


def test_nested_blocking_call_and_shutdown_fail_before_deadlocking(bridge):
    async def nested():
        coro = _answer()
        with pytest.raises(RuntimeError, match="bridge thread"):
            bridge.run(coro)
        assert coro.cr_frame is None
        with pytest.raises(RuntimeError, match="bridge thread"):
            bridge.shutdown()
        return 42

    assert bridge.run(nested(), timeout=5) == 42


async def test_sync_entry_points_can_run_from_another_event_loop(bridge):
    assert bridge.run(_answer()) == 42
    bridge.shutdown()
    assert bridge._loop.is_closed()


def test_shutdown_waits_for_task_finally_blocks(bridge):
    started = threading.Event()
    cleaned = threading.Event()

    async def wait():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0.02)
            cleaned.set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(bridge.run, wait())
        assert started.wait(5)
        bridge.shutdown()
        assert cleaned.is_set()
        with pytest.raises(concurrent.futures.CancelledError):
            result.result(5)
    assert bridge._loop.is_closed()
    assert not bridge._thread.is_alive()


def test_shutdown_does_not_cancel_a_calls_cleanup_twice(bridge):
    cleaning = threading.Event()
    cleaned = threading.Event()

    async def wait():
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await asyncio.sleep(0.05)
            cleaned.set()

    with pytest.raises(TimeoutError):
        bridge.run(wait(), timeout=0.1)
    assert cleaning.wait(5)
    bridge.shutdown()
    assert cleaned.is_set()


def test_shutdown_drains_tasks_created_during_cleanup(bridge):
    parent_started = threading.Event()
    child_started = threading.Event()
    child_cleaned = threading.Event()
    children = []

    async def child():
        try:
            child_started.set()
            await asyncio.Event().wait()
        finally:
            child_cleaned.set()

    async def parent():
        try:
            parent_started.set()
            await asyncio.Event().wait()
        finally:
            children.append(asyncio.create_task(child()))
            await asyncio.sleep(0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(bridge.run, parent())
        assert parent_started.wait(5)
        bridge.shutdown()
        with pytest.raises(concurrent.futures.CancelledError):
            result.result(5)
    assert children and all(task.done() for task in children)
    if child_started.is_set():
        assert child_cleaned.is_set()


def test_shutdown_closes_async_generators(bridge):
    cleaned = threading.Event()

    async def values():
        try:
            yield 1
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    generator = values()

    async def consume():
        return await generator.__anext__()

    assert bridge.run(consume()) == 1
    bridge.shutdown()
    assert cleaned.is_set()


def test_shutdown_timeout_can_be_retried_after_executor_finishes(bridge):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def work():
        started.set()
        release.wait(5)
        finished.set()

    async def submit_work():
        asyncio.get_running_loop().run_in_executor(None, work)

    bridge.run(submit_work())
    assert started.wait(5)
    try:
        with pytest.raises(TimeoutError, match="shutting down"):
            bridge.shutdown(timeout=0)
        coro = _answer()
        with pytest.raises(RuntimeError, match="closing or closed"):
            bridge.run(coro)
        assert coro.cr_frame is None
    finally:
        release.set()
    bridge.shutdown()
    assert finished.is_set()
    assert not bridge._thread.is_alive()


def test_concurrent_and_repeated_shutdown_is_safe(bridge):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(bridge.shutdown) for _ in range(20)]
        for future in futures:
            future.result(5)
    bridge.shutdown()
    assert bridge._loop.is_closed()
    assert not bridge._thread.is_alive()


def test_submissions_racing_with_shutdown_finish_or_fail_without_leaking(bridge):
    ready = threading.Barrier(9)

    def submit():
        coro = _answer()
        ready.wait(5)
        try:
            assert bridge.run(coro, timeout=5) == 42
        except (RuntimeError, concurrent.futures.CancelledError):
            pass
        return coro

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(submit) for _ in range(8)]
        ready.wait(5)
        bridge.shutdown()
        coroutines = [future.result(5) for future in futures]
    assert all(coro.cr_frame is None for coro in coroutines)
    assert not bridge._calls


def test_context_manager_shuts_down_after_exception():
    with pytest.raises(ValueError, match="caller failed"):
        with asyncbridge.LoopBridge() as instance:
            assert instance.run(_answer()) == 42
            raise ValueError("caller failed")
    assert instance._loop.is_closed()
    assert not instance._thread.is_alive()


def test_startup_failure_is_propagated_to_the_caller(monkeypatch):
    instance = asyncbridge.LoopBridge.__new__(asyncbridge.LoopBridge)

    def fail():
        raise OSError("no loop")

    with monkeypatch.context() as patcher:
        patcher.setattr(asyncbridge.asyncio, "new_event_loop", fail)
        with pytest.raises(RuntimeError, match="Failed to start") as exc:
            # Inspect the partially constructed instance after failure.
            instance.__init__()  # pylint: disable=unnecessary-dunder-call
    assert isinstance(exc.value.__cause__, OSError)
    assert instance._stopped.wait(5)
    instance._thread.join(5)
    assert not instance._thread.is_alive()


def test_startup_timeout_closes_a_loop_that_arrives_late(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    new_loop = asyncio.new_event_loop
    instance = asyncbridge.LoopBridge.__new__(asyncbridge.LoopBridge)

    def slow_start():
        entered.set()
        release.wait(5)
        return new_loop()

    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(asyncbridge.asyncio, "new_event_loop", slow_start)
            with pytest.raises(TimeoutError, match="starting"):
                # Inspect cleanup after the constructor has timed out.
                # pylint: disable-next=unnecessary-dunder-call
                instance.__init__(startup_timeout=0.02)
        assert entered.is_set()
    finally:
        release.set()
        assert instance._stopped.wait(5)
        instance._thread.join(5)
    assert instance._loop.is_closed()
    assert not instance._thread.is_alive()


def test_unexpected_loop_exit_wakes_an_unbounded_caller():
    instance = asyncbridge.LoopBridge()

    async def stop_loop():
        asyncio.get_running_loop().stop()
        await asyncio.Event().wait()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(instance.run, stop_loop())
        with pytest.raises(RuntimeError, match="stopped unexpectedly"):
            result.result(5)
    with pytest.raises(RuntimeError, match="stopped unexpectedly"):
        instance.shutdown()
    assert instance._loop.is_closed()
    assert not instance._thread.is_alive()


def test_shared_bridge_is_lazy_and_created_once_under_concurrency(shared_bridge):
    assert asyncbridge._bridge is None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(asyncbridge.get_bridge) for _ in range(40)]
        bridges = [future.result(5) for future in futures]
    assert len({id(instance) for instance in bridges}) == 1
    assert bridges[0].run(_answer()) == 42


def test_shared_shutdown_does_not_start_or_restart_a_loop(shared_bridge, monkeypatch):
    def unexpected_start():
        pytest.fail("shutdown must not create a loop bridge")

    monkeypatch.setattr(asyncbridge, "LoopBridge", unexpected_start)
    asyncbridge.shutdown_bridge()
    asyncbridge.shutdown_bridge()
    with pytest.raises(RuntimeError, match="shut down"):
        asyncbridge.get_bridge()


def test_shared_bridge_shutdown_closes_the_existing_instance(shared_bridge):
    instance = asyncbridge.get_bridge()
    asyncbridge.shutdown_bridge()
    asyncbridge.shutdown_bridge()
    assert instance._loop.is_closed()
    assert not instance._thread.is_alive()
    with pytest.raises(RuntimeError, match="shut down"):
        asyncbridge.get_bridge()


async def test_shared_bridge_lifecycle_from_another_event_loop(shared_bridge):
    bridge = asyncbridge.get_bridge()
    assert bridge.run(_answer()) == 42
    asyncbridge.shutdown_bridge()
    assert bridge._loop.is_closed()


def test_shared_shutdown_timeout_includes_waiting_for_the_registry(shared_bridge):
    with asyncbridge._bridge_lock:
        with pytest.raises(TimeoutError, match="shared loop bridge"):
            asyncbridge.shutdown_bridge(timeout=0)
    assert asyncbridge._bridge_shutdown is False
    assert asyncbridge.get_bridge().run(_answer()) == 42


def test_inherited_bridge_rejects_calls_before_taking_locks(bridge, monkeypatch):
    coro = _answer()
    with monkeypatch.context() as patcher:
        patcher.setattr(asyncbridge.os, "getpid", lambda: bridge.pid + 1)
        with bridge._lock:
            with pytest.raises(RuntimeError, match="before fork"):
                bridge.run(coro)
            with pytest.raises(RuntimeError, match="before fork"):
                bridge.shutdown()
    assert coro.cr_frame is None
    assert bridge.run(_answer()) == 42


def _child_bridge_probe(connection, inherited=None):
    """Top-level target also exercised with multiprocessing's spawn method."""
    try:
        if inherited is not None:
            with pytest.raises(RuntimeError, match="before fork"):
                inherited.run(_answer())
            with pytest.raises(RuntimeError, match="before fork"):
                inherited.shutdown()
        child = asyncbridge.get_bridge()
        result = child.run(_answer())
        asyncbridge.shutdown_bridge()
        connection.send((os.getpid(), result, child._loop.is_closed()))
    finally:
        connection.close()


def _process_exit_probe(connection):
    instance = asyncbridge.get_bridge()
    assert instance.run(_answer()) == 42

    def report():
        connection.send((instance._loop.is_closed(), instance._thread.is_alive()))
        connection.close()

    # The bridge's process callback has higher priority and runs first.
    multiprocessing.util.Finalize(None, report, exitpriority=0)


def test_shared_bridge_is_closed_when_a_worker_exits(shared_bridge):
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(target=_process_exit_probe, args=(sender,))
    child.start()
    sender.close()
    try:
        assert receiver.poll(10), "worker did not run process-exit cleanup"
        assert receiver.recv() == (True, False)
        child.join(5)
        assert child.exitcode == 0
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        receiver.close()


def test_explicit_shared_shutdown_unregisters_process_cleanup(shared_bridge):
    asyncbridge.get_bridge()
    finalizer = asyncbridge._bridge_finalizer
    assert finalizer.still_active()
    asyncbridge.shutdown_bridge()
    assert not finalizer.still_active()


@pytest.mark.parametrize("method", ["spawn", "fork"])
def test_child_process_gets_an_independent_bridge(shared_bridge, method):
    if method not in multiprocessing.get_all_start_methods():
        pytest.skip(f"{method} is unavailable")
    if method == "fork" and sys.platform == "darwin":
        pytest.skip("fork after threads is unsafe on macOS; exercised on Linux")
    parent = asyncbridge.get_bridge()
    context = multiprocessing.get_context(method)
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(
        target=_child_bridge_probe,
        args=(sender, parent if method == "fork" else None),
    )
    # A forked child must also reset a lock held by another parent thread.
    with asyncbridge._bridge_lock:
        child.start()
    sender.close()
    try:
        assert receiver.poll(10), "child did not complete its bridge lifecycle"
        child_pid, result, closed = receiver.recv()
        child.join(5)
        assert child.exitcode == 0
        assert child_pid != parent.pid
        assert result == 42
        assert closed
    finally:
        if child.is_alive():
            child.terminate()
            child.join(5)
        receiver.close()
    assert parent.run(_answer()) == 42


def test_completed_calls_are_released_and_rejected_coroutines_do_not_warn(bridge):
    for _ in range(100):
        assert bridge.run(_answer()) == 42
    bridge.shutdown()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="closing or closed"):
            bridge.run(_answer())
        gc.collect()
    assert not [
        warning for warning in caught if "never awaited" in str(warning.message)
    ]
    assert not bridge._calls
