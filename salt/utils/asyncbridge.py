"""
Run coroutine calls from synchronous code on a shared background loop.

The process owns the bridge, while callers own the resources they create on
it. Close those resources before shutting down the bridge. No loop or thread
is started on import, and cleanup never runs from a finalizer.
"""

import asyncio
import concurrent.futures
import math
import os
import threading
import time

_bridge = None
_bridge_lock = threading.Lock()
_bridge_shutdown = False

DEFAULT_TIMEOUT = 10


def _timeout(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Timeout must be finite and non-negative")
    return value


def _check_running_loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError("Cannot block a running event loop; await the async API")


class _Call:
    def __init__(self, coro):
        self.coro = coro
        self.future = concurrent.futures.Future()
        self.task = None
        self.cancel_requested = False


class LoopBridge:
    """
    An asyncio loop owned by a background thread.

    ``run`` accepts a coroutine and takes ownership of it, including when the
    call is rejected. A timed-out call requests cancellation; ``shutdown``
    waits for pending tasks, async generators and executor work to finish.
    A shutdown timeout leaves the bridge closing, so cleanup can finish and
    a later ``shutdown`` can wait again. It never force-closes a live loop.
    """

    def __init__(self, startup_timeout=DEFAULT_TIMEOUT):
        _check_running_loop()
        startup_timeout = _timeout(startup_timeout)
        self.pid = os.getpid()
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._loop = None
        self._closing = False
        self._error = None
        self._calls = set()
        self._thread = threading.Thread(
            target=self._run, name="salt-loop-bridge", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(startup_timeout):
            self._request_shutdown()
            raise TimeoutError("Timed out starting the loop bridge")
        if self._error is not None or self._closing:
            raise RuntimeError("Failed to start the loop bridge") from self._error

    def _check_caller(self):
        # Check the PID before touching locks inherited from another process.
        if os.getpid() != self.pid:
            raise RuntimeError("Loop bridge was created before fork; create a new one")
        if threading.current_thread() is self._thread:
            raise RuntimeError(
                "Cannot block the loop bridge thread; await the async API"
            )
        _check_running_loop()

    def run(self, coro, timeout=None):
        """
        Return a coroutine's result or propagate its exception.

        ``timeout`` is in seconds; ``None`` explicitly permits an unbounded
        operation. Shutdown or unexpected loop exit still wakes its caller.
        Cancellation is cooperative and can outlive a caller's timeout.
        """
        if not asyncio.iscoroutine(coro):
            raise TypeError("LoopBridge.run requires a coroutine")
        call = _Call(coro)
        try:
            self._check_caller()
            if timeout is not None:
                timeout = _timeout(timeout)
            with self._lock:
                if self._closing:
                    raise RuntimeError("Loop bridge is closing or closed")
                self._calls.add(call)
                try:
                    # call_soon_threadsafe copies the submitting context;
                    # the task created by _start_call inherits that context.
                    self._loop.call_soon_threadsafe(self._start_call, call)
                except BaseException:
                    self._calls.discard(call)
                    raise
        except BaseException:
            coro.close()
            raise
        try:
            return call.future.result(timeout)
        except concurrent.futures.TimeoutError as exc:
            if (
                call.future.done()
                and not call.future.cancelled()
                and call.future.exception() is exc
            ):
                raise  # The coroutine itself raised this exception.
            call.future.cancel()
            self._request_cancel(call)
            # concurrent.futures.TimeoutError became the builtin alias in
            # Python 3.11. Keep our timeout contract the same on older Python.
            raise TimeoutError("Timed out waiting for the loop bridge call") from exc
        except BaseException:
            call.future.cancel()
            self._request_cancel(call)
            raise

    def _request_cancel(self, call):
        try:
            self._loop.call_soon_threadsafe(self._cancel_call, call)
        except RuntimeError:
            pass  # The loop's final cleanup owns any remaining task.

    def _start_call(self, call):
        with self._lock:
            if call not in self._calls:
                return
        if call.future.cancelled():
            call.coro.close()
            self._forget_call(call)
            return
        try:
            call.task = self._loop.create_task(call.coro)
        except BaseException as exc:  # pylint: disable=broad-except
            call.coro.close()
            self._set_exception(call.future, exc)
            self._forget_call(call)
            return
        call.task.add_done_callback(lambda task: self._task_done(call, task))

    def _task_done(self, call, task):
        try:
            result = task.result()
        except asyncio.CancelledError:
            call.future.cancel()
        except BaseException as exc:  # pylint: disable=broad-except
            self._set_exception(call.future, exc)
        else:
            try:
                call.future.set_result(result)
            except concurrent.futures.InvalidStateError:
                pass  # The synchronous caller cancelled its wait.
        finally:
            self._forget_call(call)

    @staticmethod
    def _set_exception(future, exc):
        try:
            future.set_exception(exc)
        except concurrent.futures.InvalidStateError:
            pass  # The synchronous caller cancelled its wait.

    def _forget_call(self, call):
        with self._lock:
            self._calls.discard(call)

    @staticmethod
    def _cancel_call(call):
        if call.task is not None and not call.task.done() and not call.cancel_requested:
            call.cancel_requested = True
            call.task.cancel()

    def _request_shutdown(self):
        with self._lock:
            if self._closing:
                return
            self._closing = True
            if self._loop is not None and not self._stopped.is_set():
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except RuntimeError:
                    pass  # The loop already stopped after a failure.

    def shutdown(self, timeout=DEFAULT_TIMEOUT):
        """Stop accepting calls and wait at most ``timeout`` seconds for cleanup."""
        self._check_caller()
        deadline = time.monotonic() + _timeout(timeout)
        # Only the first request stops run_forever. Repeated requests must
        # not stop the loop again while it is awaiting shutdown cleanup.
        self._request_shutdown()
        self._thread.join(max(0, deadline - time.monotonic()))
        if self._thread.is_alive():
            raise TimeoutError("Timed out shutting down the loop bridge")
        if self._error is not None:
            raise RuntimeError("Loop bridge stopped unexpectedly") from self._error

    def _cancel_calls(self):
        with self._lock:
            calls = list(self._calls)
        for call in calls:
            if call.task is None:
                call.coro.close()
                self._forget_call(call)
            if self._error is None:
                call.future.cancel()
            else:
                self._set_exception(call.future, self._error)
            self._cancel_call(call)

    async def _drain_tasks(self):
        current = asyncio.current_task()
        while tasks := asyncio.all_tasks() - {current}:
            with self._lock:
                # Do not interrupt a cancelled call's finally block.
                calls = {call.task for call in self._calls}
            for task in tasks - calls:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _drain(self):
        await self._drain_tasks()
        await self._loop.shutdown_asyncgens()
        await self._loop.shutdown_default_executor()
        await self._drain_tasks()

    def _run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with self._lock:
                self._loop = loop
                closing = self._closing
            if not closing:
                loop.call_soon(self._ready.set)
                loop.run_forever()
        except BaseException as exc:  # pylint: disable=broad-except
            self._error = exc
        finally:
            with self._lock:
                if not self._closing and self._error is None:
                    self._error = RuntimeError(
                        "Loop bridge event loop stopped unexpectedly"
                    )
                self._closing = True
            self._ready.set()  # Also wake construction on startup failure.
            self._cancel_calls()
            try:
                if loop is not None:
                    loop.run_until_complete(self._drain())
            except BaseException as exc:  # pylint: disable=broad-except
                self._error = exc
            finally:
                try:
                    if loop is not None:
                        loop.close()
                except BaseException as exc:  # pylint: disable=broad-except
                    self._error = exc
                finally:
                    asyncio.set_event_loop(None)
                    self._stopped.set()

    def __enter__(self):
        self._check_caller()
        return self

    def __exit__(self, *_):
        self.shutdown()


def get_bridge():
    """Lazily return this process's shared bridge until explicit shutdown."""
    global _bridge
    _check_running_loop()
    with _bridge_lock:
        if _bridge_shutdown:
            raise RuntimeError("Shared loop bridge has been shut down")
        if _bridge is None:
            _bridge = LoopBridge()
        return _bridge


def shutdown_bridge(timeout=DEFAULT_TIMEOUT):
    """Shut down the shared bridge without starting one or permitting a restart."""
    global _bridge_shutdown
    _check_running_loop()
    timeout = _timeout(timeout)
    deadline = time.monotonic() + timeout
    if not _bridge_lock.acquire(timeout=timeout):
        raise TimeoutError("Timed out shutting down the shared loop bridge")
    try:
        _bridge_shutdown = True
        bridge = _bridge
    finally:
        _bridge_lock.release()
    if bridge is not None:
        bridge.shutdown(max(0, deadline - time.monotonic()))


def _reset_after_fork():
    global _bridge, _bridge_lock, _bridge_shutdown
    _bridge = None
    _bridge_lock = threading.Lock()
    _bridge_shutdown = False


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)
