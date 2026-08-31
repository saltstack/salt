"""
Helpers/utils for working with tornado asynchronous stuff
"""

import asyncio
import contextlib
import gc
import logging
import sys
import threading
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
                    gathered = asyncio.gather(*pending_tasks, return_exceptions=True)
                    try:
                        self.asyncio_loop.run_until_complete(gathered)
                    except Exception:  # pylint: disable=broad-except
                        # ``gathered`` is a Future; if run_until_complete bailed
                        # part-way we still need to make sure the Future is
                        # consumed so its exception (if any) isn't logged as
                        # unhandled.  Tasks already cancelled above.
                        if not gathered.done():
                            gathered.cancel()

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
        # PATCH: mirror ``SaltEvent.__del__`` at ``salt/utils/event.py``
        # -- deliberately do NOT close the wrapped ``obj`` / io_loop /
        # asyncio_loop from ``__del__``.  ``__del__`` fires during GC
        # (may be arbitrarily delayed, may skip on reference cycles)
        # and during interpreter shutdown, when the world is already
        # tearing down and touching a tornado/asyncio loop can raise
        # from a partially-freed C extension.  Instead, emit a
        # ``ResourceWarning`` so callers that missed ``close()`` /
        # context-manager surface loudly in tests / sentry / log
        # aggregators.
        #
        # Motivation: ``SyncWrapper``-owned asyncio loops are the
        # dominant leak surface on the minion under sustained
        # ``saltutil.refresh_pillar`` / re-auth churn -- each abandoned
        # wrapper holds a whole IOLoop, its ZMQ context, and the two
        # socketpairs backing the master REQ channel.  Observed ~451
        # leaked socketpairs (~902 fds) per minion, tripping the
        # 1024-file ulimit critical threshold and the minion's own
        # sock-throttle logic.
        try:
            unclosed = getattr(self, "obj", None) is not None or (
                getattr(self, "asyncio_loop", None) is not None
                and not self.asyncio_loop.is_closed()
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

    # pylint: enable=W1701
