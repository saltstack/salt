"""
Async utilities and compatibility helpers for Salt.

This module historically wrapped Tornado's ``IOLoop`` so synchronous code could
interact with async transports. As Salt moves toward ``asyncio`` we provide a
small adapter which mirrors the Tornado APIs still referenced in the codebase
while delegating work to an ``asyncio`` event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import threading
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any

try:  # Optional dependency during the transition away from tornado.
    import tornado  # type: ignore
    import tornado.concurrent  # type: ignore
    import tornado.ioloop  # type: ignore
    from tornado.platform.asyncio import to_asyncio_future  # type: ignore
except ImportError:  # pragma: no cover - tornado optional
    tornado = None  # type: ignore
    to_asyncio_future = None  # type: ignore
    _TORNADO_FUTURE_TYPES: tuple[type[Any], ...] = ()
else:
    _TORNADO_FUTURE_TYPES = (tornado.concurrent.Future,)  # type: ignore[attr-defined]

log = logging.getLogger(__name__)


def _ensure_task(loop: asyncio.AbstractEventLoop, result: Any) -> Any:
    """
    Schedule ``result`` on ``loop`` when it is a coroutine/future, otherwise
    return it unchanged.
    """

    if asyncio.iscoroutine(result):
        return asyncio.ensure_future(result, loop=loop)

    if isinstance(result, asyncio.Future):
        try:
            future_loop = result.get_loop()
        except AttributeError:
            future_loop = loop
        if future_loop is loop:
            return asyncio.ensure_future(result, loop=loop)

        proxy = loop.create_future()

        def _relay(src_future: asyncio.Future):
            if proxy.done():
                return
            if src_future.cancelled():
                loop.call_soon_threadsafe(proxy.cancel)
                return
            exc = src_future.exception()
            if exc is not None:
                loop.call_soon_threadsafe(proxy.set_exception, exc)
                return
            loop.call_soon_threadsafe(proxy.set_result, src_future.result())

        result.add_done_callback(_relay)
        return proxy

    if _TORNADO_FUTURE_TYPES and isinstance(
        result, _TORNADO_FUTURE_TYPES  # type: ignore[arg-type]
    ):
        converted = None
        if to_asyncio_future is not None:
            try:
                converted = to_asyncio_future(result)
            except TypeError:
                converted = None
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "Failed to convert future %r to asyncio future using tornado helper",
                    result,
                )
        if converted is not None:
            try:
                return asyncio.ensure_future(converted, loop=loop)
            except TypeError:
                converted = None
        if converted is None:
            converted = loop.create_future()

            def _relay(src_future):
                if converted.done():
                    return
                if src_future.cancelled():
                    loop.call_soon_threadsafe(converted.cancel)
                    return
                exc = src_future.exception()
                if exc is not None:
                    loop.call_soon_threadsafe(converted.set_exception, exc)
                    return
                loop.call_soon_threadsafe(converted.set_result, src_future.result())

            result.add_done_callback(_relay)
        return asyncio.ensure_future(converted, loop=loop)

    if hasattr(result, "add_done_callback"):
        try:
            wrapped = asyncio.wrap_future(result, loop=loop)
            return asyncio.ensure_future(wrapped, loop=loop)
        except TypeError:
            bridge = loop.create_future()

            def _relay(src_future):
                if bridge.done():
                    return
                if getattr(src_future, "cancelled", lambda: False)():
                    loop.call_soon_threadsafe(bridge.cancel)
                    return
                exc = getattr(src_future, "exception", lambda: None)()
                if exc is not None:
                    loop.call_soon_threadsafe(bridge.set_exception, exc)
                    return
                result_value = getattr(src_future, "result", lambda: None)()
                loop.call_soon_threadsafe(bridge.set_result, result_value)

            result.add_done_callback(_relay)
            return bridge

    return result


class AsyncLoopAdapter:
    """
    A light-weight adapter exposing the subset of Tornado's ``IOLoop`` API that
    Salt still depends on, backed by an ``asyncio`` event loop.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop or asyncio.new_event_loop()

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------
    @property
    def asyncio_loop(self) -> asyncio.AbstractEventLoop:
        return self._loop

    def time(self) -> float:
        return self._loop.time()

    # ------------------------------------------------------------------
    # Scheduling primitives
    # ------------------------------------------------------------------
    def spawn_callback(self, callback: Callable[..., Any], *args, **kwargs):
        if asyncio.iscoroutinefunction(callback):

            def run_async():
                self._loop.create_task(callback(*args, **kwargs))

            self._loop.call_soon(run_async)
            return

        def run_sync():
            try:
                result = callback(*args, **kwargs)
            except Exception:  # pylint: disable=broad-except
                log.exception("Exception in spawn_callback")
                return
            _ensure_task(self._loop, result)

        self._loop.call_soon(run_sync)

    def add_callback(self, callback: Callable[..., Any], *args, **kwargs):
        if asyncio.iscoroutinefunction(callback):
            self._loop.call_soon(
                lambda: self._loop.create_task(callback(*args, **kwargs))
            )
        else:
            self._loop.call_soon(callback, *args, **kwargs)

    def call_later(self, delay: float, callback: Callable[..., Any], *args, **kwargs):
        if asyncio.iscoroutinefunction(callback):

            def runner():
                self._loop.create_task(callback(*args, **kwargs))

            return self._loop.call_later(delay, runner)
        return self._loop.call_later(delay, callback, *args, **kwargs)

    def add_timeout(self, when: float, callback: Callable[..., Any], *args, **kwargs):
        delay = max(0.0, when - self._loop.time())
        return self.call_later(delay, callback, *args, **kwargs)

    def remove_timeout(self, handle: asyncio.TimerHandle):
        handle.cancel()

    def add_future(self, future: Awaitable, callback: Callable[[asyncio.Future], Any]):
        scheduled = _ensure_task(self._loop, future)
        if isinstance(scheduled, asyncio.Future):
            scheduled.add_done_callback(
                lambda done: self._loop.call_soon(callback, done)
            )
            return scheduled
        if hasattr(scheduled, "add_done_callback"):

            def _relay(done):
                try:
                    loop = self._loop
                    loop.call_soon_threadsafe(callback, done)
                except RuntimeError:
                    loop.call_soon(callback, done)

            scheduled.add_done_callback(_relay)
        return scheduled

    def create_task(self, coro: Awaitable):
        return self._loop.create_task(coro)

    # ------------------------------------------------------------------
    # Loop control
    # ------------------------------------------------------------------
    def run_sync(
        self,
        func: Callable[..., Awaitable],
        *args,
        **kwargs,
    ):
        result = func(*args, **kwargs)
        scheduled = _ensure_task(self._loop, result)
        if asyncio.iscoroutine(scheduled) or isinstance(scheduled, asyncio.Future):
            if self._loop.is_running():
                raise RuntimeError("Cannot run_sync on a running event loop")
            policy = asyncio.get_event_loop_policy()
            try:
                policy.set_event_loop(self._loop)
                return self._loop.run_until_complete(scheduled)
            finally:
                policy.set_event_loop(None)
        return scheduled

    def start(self):
        policy = asyncio.get_event_loop_policy()
        try:
            policy.set_event_loop(self._loop)
            self._loop.run_forever()
        finally:
            policy.set_event_loop(None)

    def stop(self):
        self._loop.stop()

    def close(self, all_fds: bool = False):  # pylint: disable=unused-argument
        self._loop.close()


def get_io_loop(io_loop: Any | None = None) -> AsyncLoopAdapter:
    """
    Normalize ``io_loop`` into an :class:`AsyncLoopAdapter`.

    Accepts an existing adapter, a raw ``asyncio`` loop, an object exposing an
    ``asyncio_loop`` attribute (e.g. Tornado's ``IOLoop``), or ``None`` in which
    case a running loop is wrapped or a new loop is created.
    """

    if isinstance(io_loop, AsyncLoopAdapter):
        return io_loop

    if isinstance(io_loop, asyncio.AbstractEventLoop):
        return AsyncLoopAdapter(io_loop)

    if io_loop is not None and hasattr(io_loop, "asyncio_loop"):
        candidate_loop = getattr(io_loop, "asyncio_loop")
        if isinstance(candidate_loop, AsyncLoopAdapter):
            return candidate_loop
        if isinstance(candidate_loop, asyncio.AbstractEventLoop):
            return AsyncLoopAdapter(candidate_loop)
        # Objects such as mocks may expose ``asyncio_loop`` even though they do
        # not wrap a real loop. In that case, fall back to creating a fresh loop.

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    return AsyncLoopAdapter(loop)


def aioloop(io_loop: Any | None = None, warn: bool = False):
    """
    Compatibility helper returning the underlying ``asyncio`` loop.
    """

    if warn and tornado is not None and isinstance(io_loop, tornado.ioloop.IOLoop):
        log.warning("Tornado IOLoop provided; returning underlying asyncio loop")
    return get_io_loop(io_loop).asyncio_loop


@contextlib.contextmanager
def current_ioloop(io_loop: Any):
    """
    Temporarily install ``io_loop`` (adapter or compatible object) as the
    current asyncio loop.
    """

    adapter = get_io_loop(io_loop)
    policy = asyncio.get_event_loop_policy()
    try:
        previous = policy.get_event_loop()
    except RuntimeError:
        previous = None

    policy.set_event_loop(adapter.asyncio_loop)
    try:
        yield
    finally:
        if previous is None:
            policy.set_event_loop(None)
        else:
            policy.set_event_loop(previous)


class SyncWrapper:
    """
    Wrap asynchronous classes behind a synchronous facade.
    """

    def __init__(
        self,
        cls,
        args=None,
        kwargs=None,
        async_methods=None,
        close_methods=None,
        loop_kwarg=None,
    ):
        self.asyncio_loop = asyncio.new_event_loop()
        self.io_loop = AsyncLoopAdapter(self.asyncio_loop)
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        if async_methods is None:
            async_methods = []
        if close_methods is None:
            close_methods = []
        self.loop_kwarg = loop_kwarg
        self.cls = cls
        if loop_kwarg:
            kwargs[self.loop_kwarg] = self.io_loop
        with current_ioloop(self.io_loop):
            self.obj = cls(*args, **kwargs)
        self._async_methods = list(
            set(async_methods + getattr(self.obj, "async_methods", []))
        )
        self._close_methods = list(
            set(close_methods + getattr(self.obj, "close_methods", []))
        )

    def _populate_async_methods(self):
        if hasattr(self.obj, "_coroutines"):
            self._async_methods += self.obj._coroutines

    def __repr__(self):
        return f"<SyncWrapper(cls={self.cls})"

    def close(self):
        for method in self._close_methods:
            if method in self._async_methods:
                method = self._wrap(method)
            else:
                try:
                    method = getattr(self.obj, method)
                except AttributeError:
                    log.error("No sync method %s on object %r", method, self.obj)
                    continue
            try:
                result = method()
                if asyncio.iscoroutine(result) or isinstance(result, asyncio.Future):
                    self.io_loop.run_sync(lambda res=result: res)
            except AttributeError:
                log.error("No async method %s on object %r", method, self.obj)
            except Exception:  # pylint: disable=broad-except
                log.exception("Exception encountered while running stop method")
        io_loop = self.io_loop
        io_loop.stop()
        try:
            io_loop.close()
        except KeyError:
            pass
        self.asyncio_loop.close()

    def __getattr__(self, key):
        if key in self._async_methods:
            return self._wrap(key)
        return getattr(self.obj, key)

    def _wrap(self, key):
        def wrap(*args, **kwargs):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return self.io_loop.run_sync(
                    partial(getattr(self.obj, key), *args, **kwargs)
                )
            results = []
            thread = threading.Thread(
                target=self._target,
                args=(key, args, kwargs, results, self.asyncio_loop),
            )
            thread.start()
            thread.join()
            if results[0]:
                return results[1]
            exc_info = results[1]
            raise exc_info[1].with_traceback(exc_info[2])

        return wrap

    def _target(self, key, args, kwargs, results, asyncio_loop):
        policy = asyncio.get_event_loop_policy()
        policy.set_event_loop(asyncio_loop)
        adapter = AsyncLoopAdapter(asyncio_loop)
        try:
            result = adapter.run_sync(partial(getattr(self.obj, key), *args, **kwargs))
            results.append(True)
            results.append(result)
        except Exception:  # pylint: disable=broad-except
            results.append(False)
            results.append(sys.exc_info())
        finally:
            policy.set_event_loop(None)

    def __enter__(self):
        if hasattr(self.obj, "__aenter__"):
            ret = self._wrap("__aenter__")()
            if ret == self.obj:
                return self
            return ret
        if hasattr(self.obj, "__enter__"):
            ret = self.obj.__enter__()
            if ret == self.obj:
                return self
            return ret
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if hasattr(self.obj, "__aexit__"):
            self._wrap("__aexit__")(exc_type, exc_val, tb)
        self.close()
