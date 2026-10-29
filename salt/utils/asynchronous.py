"""
Helpers for asyncio, Tornado and synchronous execution boundaries
"""

import asyncio
import concurrent.futures
import contextlib
import gc
import logging
import math
import multiprocessing.util
import os
import sys
import threading
import time
import types

import tornado.concurrent
import tornado.ioloop

import salt.utils.resource_warnings

log = logging.getLogger(__name__)


def aioloop(io_loop, warn=False):
    """
    Ensure the ioloop is an asyncio loop not a tornado ioloop.
    """
    if isinstance(io_loop, asyncio.AbstractEventLoop):
        return io_loop
    elif isinstance(io_loop, tornado.ioloop.IOLoop):
        if warn:
            import traceback

            log.warning("Passed tornado loop %s", "".join(traceback.format_stack()))
        return io_loop.asyncio_loop
    else:
        raise RuntimeError("Loop must be AbstractEventLoop (prefered) or IOLoop")


@contextlib.contextmanager
def current_ioloop(io_loop):
    """
    A context manager that will set the current ioloop to io_loop for the context
    """
    try:
        # Use instance=False to avoid auto-creating a default IOLoop that leaks FDs
        orig_loop = tornado.ioloop.IOLoop.current(instance=False)
    except RuntimeError:
        orig_loop = None

    # Normalize io_loop to asyncio loop
    asyncio_loop = aioloop(io_loop)
    asyncio.set_event_loop(asyncio_loop)
    try:
        yield
    finally:
        if orig_loop:
            asyncio.set_event_loop(aioloop(orig_loop))
        else:
            asyncio.set_event_loop(None)


class SyncWrapper:
    """
    A wrapper to make Async classes synchronous

    This is uses as a simple wrapper, for example:

    asynchronous = AsyncClass()
    # this method would regularly return a future
    future = asynchronous.async_method()

    sync = SyncWrapper(async_factory_method, (arg1, arg2), {'kwarg1': 'val'})
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
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
        self.io_loop = tornado.ioloop.IOLoop(
            asyncio_loop=self.asyncio_loop, make_current=False
        )
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
        # Record creating pid so a forked child that inherits this wrapper via
        # copy-on-write does NOT touch (close) or warn on the wrapped ``obj`` +
        # io_loop + asyncio_loop in its ``__del__`` -- the parent still owns
        # them; closing the wrapped socket FDs from the child would break the
        # parent's transport (observed in tests/pytests/unit/utils/event/
        # test_event.py::test_event_no_timeout when ``EventSender``'s fork
        # inherited the ``MasterEvent`` subscriber ``SyncWrapper`` and, on
        # exit, GC-closed the shared IPC socket).  Same rationale + pattern
        # as the transport classes in ``salt/transport/tcp.py``.
        self._creator_pid = os.getpid()
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
        """
        We need the '_coroutines' attribute on classes until we can depricate
        tornado<4.5. After that 'is_coroutine_fuction' will always be
        available.
        """
        if hasattr(self.obj, "_coroutines"):
            self._async_methods += self.obj._coroutines

    def __repr__(self):
        return f"<SyncWrapper(cls={self.cls})"

    @staticmethod
    def _loop_can_run_until_complete(loop):
        """
        Return ``True`` iff ``loop.run_until_complete(coro)`` can drive a
        freshly created coroutine to completion without immediately raising.

        ``BaseEventLoop.run_until_complete`` raises ``RuntimeError`` if the
        loop is closed or already running, but only *after* its
        ``future`` argument has been evaluated.  Constructing the
        coroutine without being able to await it leaks it through
        ``coroutine.__del__`` as ``RuntimeWarning: coroutine '...' was
        never awaited`` (see ``close()``).  We avoid that by inspecting
        the loop's state up front.
        """
        if loop is None:
            return False
        if loop.is_closed():
            return False
        if loop.is_running():
            return False
        return True

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
                method()
            except AttributeError:
                log.error("No async method %s on object %r", method, self.obj)
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    "Exception encountered while running stop method: %s", exc
                )
        # Shut down asyncio resources before closing the IOLoop so file descriptors
        # held by pending tasks, async generators, and the default executor are released.
        #
        # Each of the three ``run_until_complete`` calls below takes a freshly
        # constructed coroutine object as its argument.  If the loop is already
        # closed (or running) at that point ``run_until_complete`` raises
        # ``RuntimeError`` *after* the coroutine has been created but *before*
        # ``ensure_future`` wraps it — and the bare coroutine object is then
        # garbage-collected unawaited, emitting a
        # ``RuntimeWarning: coroutine '...' was never awaited`` on stderr.  On
        # Python 3.14 / Windows the batch CLI integration tests
        # (``tests/pytests/integration/cli/test_batch.py::test_batch_retcode``
        # and ``test_multiple_modules_in_batch``) gate on ``assert not
        # cmd.stderr`` and turn that warning into a hard failure.
        #
        # Gate every call on ``not _loop_can_run_until_complete(loop)`` so we
        # never even *construct* the inner coroutine when the loop can't drive
        # it to completion.
        try:
            if self._loop_can_run_until_complete(self.asyncio_loop):
                pending_tasks = [
                    task
                    for task in asyncio.all_tasks(self.asyncio_loop)
                    if not task.done()
                ]
                if pending_tasks:
                    for task in pending_tasks:
                        task.cancel()

                    # ``asyncio.gather`` has no ``loop`` argument any more, so it
                    # resolves the loop from the calling context.  ``close()``
                    # runs outside ``self.asyncio_loop`` -- the thread's current
                    # loop is a different one -- so on Python 3.14 gathering
                    # tasks that belong to ``self.asyncio_loop`` raises
                    # ``ValueError: The future belongs to a different loop than
                    # the one specified as the loop argument``.  Earlier versions
                    # took the loop from the first future and let it pass.
                    #
                    # Build the gather *inside* the loop instead, where the
                    # running loop is the right one on every version.
                    async def _drain(tasks):
                        await asyncio.gather(*tasks, return_exceptions=True)

                    drain = _drain(pending_tasks)
                    try:
                        self.asyncio_loop.run_until_complete(drain)
                    except Exception:  # pylint: disable=broad-except
                        # Close the coroutine we just built so it is not
                        # garbage-collected unawaited, which would emit a
                        # RuntimeWarning on stderr.  Tasks already cancelled.
                        drain.close()

            if self._loop_can_run_until_complete(self.asyncio_loop):
                shutdown_agens = self.asyncio_loop.shutdown_asyncgens()
                try:
                    self.asyncio_loop.run_until_complete(shutdown_agens)
                except Exception:  # pylint: disable=broad-except
                    shutdown_agens.close()

            if self._loop_can_run_until_complete(self.asyncio_loop):
                shutdown_exec = self.asyncio_loop.shutdown_default_executor()
                try:
                    self.asyncio_loop.run_until_complete(shutdown_exec)
                except Exception:  # pylint: disable=broad-except
                    shutdown_exec.close()

        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error during asyncio shutdown: %s", exc)

        io_loop = self.io_loop
        try:
            io_loop.stop()
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Error stopping IOLoop: %s", exc)
        try:
            io_loop.close(all_fds=True)
        except KeyError:
            pass
        except Exception as exc:  # pylint: disable=broad-except
            log.error("Unexpected error closing IOLoop: %s", exc)

        if not self.asyncio_loop.is_closed():
            try:
                self.asyncio_loop.close()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error closing asyncio loop: %s", exc)

        self.obj = None
        self.io_loop = None
        self.asyncio_loop = None

    def __getattr__(self, key):
        if key in self._async_methods:
            return self._wrap(key)
        return getattr(self.obj, key)

    def _wrap(self, key):
        def wrap(*args, **kwargs):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # asyncio.get_running_loop() raises RuntimeError
                # if there is no running loop, so we can run the method
                # directly with no detaching it to the distinct thread.
                # It will make SyncWrapper way faster for the cases
                # when there are no nested SyncWrapper objects used.
                return self.io_loop.run_sync(
                    lambda: getattr(self.obj, key)(*args, **kwargs)
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
            else:
                exc_info = results[1]
                raise exc_info[1].with_traceback(exc_info[2])

        return wrap

    # Referrer types considered "internal" for the purposes of orphan-task
    # detection in ``_target``.  A Task with only these referrers has no
    # user-owned strong reference and can be safely cancelled after
    # ``run_sync`` returns.  A Task with any *other* referrer is assumed
    # to be intentionally held by the wrapped object (e.g. ``PublishClient``
    # stores its persistent ``_read_into_unpacker`` task as
    # ``self._read_task`` so that subsequent ``recv()`` calls can wait
    # on it -- cancelling that task mid-lifecycle leaves the underlying
    # ``tornado.iostream.IOStream._read_future`` set, and the next
    # ``recv()`` fails with ``AssertionError: Already reading``).
    _ORPHAN_TASK_REFERRER_TYPES = (
        set,
        list,
        tuple,
        frozenset,
        dict,
        asyncio.Task,
        asyncio.Future,
        types.CoroutineType,
        types.FrameType,
        types.MethodType,
        types.BuiltinMethodType,
    )

    @classmethod
    def _task_is_orphan(cls, task, exclude):
        """
        Return ``True`` iff the only strong references to ``task`` are
        internal asyncio / GC machinery -- i.e. no user object holds
        the task as an attribute.

        ``exclude`` is a set of ``id()`` values for referrers the caller
        knows about (e.g. the local ``new_tasks`` list) and wants
        ignored.  ``TaskStepMethWrapper`` is not importable at module
        scope on every Python; filter it by class ``__name__``.
        """
        for ref in gc.get_referrers(task):
            if id(ref) in exclude:
                continue
            if isinstance(ref, cls._ORPHAN_TASK_REFERRER_TYPES):
                continue
            # ``TaskStepMethWrapper`` is a C-level asyncio internal used
            # to bind ``Task.__step`` as a callback on the awaited future
            # -- it does not indicate user ownership.
            if type(ref).__name__ == "TaskStepMethWrapper":
                continue
            return False
        return True

    def _target(self, key, args, kwargs, results, asyncio_loop):
        asyncio.set_event_loop(asyncio_loop)
        io_loop = tornado.ioloop.IOLoop.current()
        # Snapshot pre-existing tasks so we only consider ones this
        # ``run_sync`` created.  ``asyncio.all_tasks`` returns tasks whose
        # ``get_loop()`` is ``asyncio_loop``; this is safe to call from a
        # worker thread as long as we're not mid-modification of the loop's
        # task registry -- which we aren't, since the loop isn't running
        # yet in this thread.
        try:
            pre_existing = set(asyncio.all_tasks(asyncio_loop))
        except RuntimeError:
            pre_existing = set()
        try:
            result = io_loop.run_sync(lambda: getattr(self.obj, key)(*args, **kwargs))
            results.append(True)
            results.append(result)
        except Exception:  # pylint: disable=broad-except
            results.append(False)
            results.append(sys.exc_info())
        finally:
            # Reap ``asyncio.Task`` objects the wrapped coroutine scheduled
            # on ``asyncio_loop`` but did not await -- e.g. pyzmq's
            # future-based sockets and tornado's asyncio bridge fire tasks
            # on the current asyncio loop that outlive the ``run_sync``
            # window.  Without this the Task pins its coroutine +
            # ``contextvars.Context`` until ``close()``, which long-lived
            # driver processes (``EventReturn``, ``BatchManager``) don't
            # call in steady state.
            #
            # We only cancel tasks that (a) did not exist before this
            # ``run_sync`` call and (b) have no user-object strong
            # reference (i.e. weren't stored as an attribute on the
            # wrapped object).  Blanket-cancelling every pending task
            # breaks clients like ``salt.transport.tcp.PublishClient``
            # which keep a persistent ``_read_into_unpacker`` task in
            # flight across multiple ``recv()`` calls -- cancelling it
            # leaves ``tornado.iostream.IOStream._read_future`` set and
            # the next ``recv()`` fails ``AssertionError: Already
            # reading``.
            try:
                if self._loop_can_run_until_complete(asyncio_loop):
                    try:
                        current = asyncio.all_tasks(asyncio_loop)
                    except RuntimeError:
                        current = set()
                    new_tasks = [
                        task
                        for task in current
                        if task not in pre_existing and not task.done()
                    ]
                    if new_tasks:
                        exclude = {id(new_tasks), id(current), id(pre_existing)}
                        orphans = [
                            task
                            for task in new_tasks
                            if self._task_is_orphan(task, exclude)
                        ]
                        if orphans:
                            for task in orphans:
                                task.cancel()
                            gathered = asyncio.gather(*orphans, return_exceptions=True)
                            try:
                                asyncio_loop.run_until_complete(gathered)
                            except Exception:  # pylint: disable=broad-except
                                if not gathered.done():
                                    gathered.cancel()
            except Exception as exc:  # pylint: disable=broad-except
                log.error("Error reaping asyncio tasks after run_sync: %s", exc)

    def __enter__(self):
        if hasattr(self.obj, "__aenter__"):
            ret = self._wrap("__aenter__")()
            if ret == self.obj:
                return self
            else:
                return ret
        elif hasattr(self.obj, "__enter__"):
            ret = self.obj.__enter__()
            if ret == self.obj:
                return self
            else:
                return ret
        return self

    def __exit__(self, exc_type, exc_val, tb):
        if hasattr(self.obj, "__aexit__"):
            self._wrap("__aexit__")(exc_type, exc_val, tb)
        self.close()

    # pylint: disable=W1701
    def __del__(self):
        # On this LTS branch ``__del__`` both surfaces the leak via
        # ``warn_until_close`` (loud WARNING-level log record and
        # ``ResourceWarning``) AND falls back to calling ``close()`` as
        # a safety net, so callers that historically relied on GC-time
        # cleanup do not silently leak a whole ``asyncio`` event loop,
        # its tornado IOLoop, and the ZMQ context / socketpairs backing
        # the wrapped async object (typically ``AsyncReqChannel``,
        # ``AsyncPubChannel`` or ``AsyncEventPublisher``).
        #
        # Motivation: ``SyncWrapper``-owned asyncio loops are the
        # dominant leak surface on the minion under sustained
        # ``saltutil.refresh_pillar`` / re-auth churn -- each abandoned
        # wrapper holds a whole IOLoop, its ZMQ context, and the two
        # socketpairs backing the master REQ channel.  Observed ~451
        # leaked socketpairs (~902 fds) per minion, tripping the
        # 1024-file ulimit critical threshold and the minion's own
        # sock-throttle logic.
        #
        # The companion change on ``master`` (Potassium) drops the
        # ``close()`` fallback and requires callers to use a context
        # manager or explicit ``close()``; the loud warning here is the
        # migration signal for that change.
        #
        # Python's ``__del__`` runs during GC (may be delayed, may skip
        # on reference cycles) and during interpreter shutdown (when the
        # world is already tearing down and touching a tornado/asyncio
        # loop can raise from a partially-freed C extension).  The
        # ``close()`` call chain below is guarded so a finalizer never
        # propagates an exception.
        #
        # Use ``self.__dict__.get(...)`` rather than ``getattr()`` for the
        # attribute probes below: ``SyncWrapper.__getattr__`` delegates
        # missing attributes to ``self.obj``, so a partially-initialized
        # instance (``object.__new__`` bypass, or ``__init__`` raised
        # before ``self.obj`` was assigned) would recurse infinitely
        # through ``__getattr__`` while the finalizer is running.
        _creator_pid = self.__dict__.get("_creator_pid")
        if _creator_pid is not None and os.getpid() != _creator_pid:
            # Forked child: the parent still owns the wrapped ``obj`` /
            # io_loop / asyncio_loop; do NOT touch them here (that would
            # break the parent's transport by closing shared FDs) and do
            # NOT emit a leak warning (this wrapper is not our
            # responsibility).  Same rationale as the transport-class
            # ``__del__`` guards for Subscriber / TCPPuller /
            # PublishServer / _TCPPubServerPublisher.
            return
        try:
            _obj = self.__dict__.get("obj")
            _asyncio_loop = self.__dict__.get("asyncio_loop")
            unclosed = _obj is not None or (
                _asyncio_loop is not None and not _asyncio_loop.is_closed()
            )
        except Exception:  # pylint: disable=broad-except
            return
        if not unclosed:
            return
        salt.utils.resource_warnings.warn_until_close(
            f"unclosed {type(self).__name__} for cls="
            f"{getattr(self, 'cls', None)!r}; call ``close()`` or "
            f"use as a context manager",
            source=self,
            log=log,
        )
        try:
            self.close()
        except Exception:  # pylint: disable=broad-except
            # Finalizer must never raise.  ``close()`` is itself heavily
            # guarded at each step (see the try/except-pass around every
            # ``run_until_complete`` / ``io_loop.close`` call) so we do
            # not expect to reach this outer handler in normal flow --
            # it is a last resort for partially-freed C extensions
            # during interpreter shutdown.
            pass

    # pylint: enable=W1701


_bridge = None
_bridge_lock = threading.Lock()
_bridge_shutdown = False
_bridge_finalizer = None

DEFAULT_TIMEOUT = 10


def _timeout(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("Timeout must be finite and non-negative")
    return value


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
    Synchronous entry points may use it from another running event loop;
    that caller still blocks. Native async callers should await their API.
    """

    def __init__(self, startup_timeout=DEFAULT_TIMEOUT):
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
    global _bridge, _bridge_finalizer
    with _bridge_lock:
        if _bridge_shutdown:
            raise RuntimeError("Shared loop bridge has been shut down")
        if _bridge is None:
            _bridge = LoopBridge()
            # No weakref target: this runs on process exit, not during GC.
            # multiprocessing also runs it before a worker calls os._exit().
            _bridge_finalizer = multiprocessing.util.Finalize(
                None, shutdown_bridge, exitpriority=10
            )
        return _bridge


def shutdown_bridge(timeout=DEFAULT_TIMEOUT):
    """Shut down the shared bridge without starting one or permitting a restart."""
    global _bridge_shutdown
    timeout = _timeout(timeout)
    deadline = time.monotonic() + timeout
    if not _bridge_lock.acquire(timeout=timeout):
        raise TimeoutError("Timed out shutting down the shared loop bridge")
    try:
        if _bridge is not None:
            _bridge._check_caller()
        _bridge_shutdown = True
        bridge = _bridge
        finalizer = _bridge_finalizer
    finally:
        _bridge_lock.release()
    if bridge is not None:
        bridge.shutdown(max(0, deadline - time.monotonic()))
    if finalizer is not None:
        finalizer.cancel()


def _reset_after_fork():
    global _bridge, _bridge_lock, _bridge_shutdown, _bridge_finalizer
    _bridge = None
    _bridge_lock = threading.Lock()
    _bridge_shutdown = False
    _bridge_finalizer = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)
