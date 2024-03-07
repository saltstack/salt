"""
Helpers/utils for working with tornado asynchronous stuff
"""

import asyncio
import contextlib
import logging
import sys
import threading

import tornado.concurrent
import tornado.ioloop

log = logging.getLogger(__name__)


@contextlib.contextmanager
def current_ioloop(io_loop):
    """
    A context manager that will set the current ioloop to io_loop for the context
    """
    try:
        orig_loop = tornado.ioloop.IOLoop.current()
    except RuntimeError:
        orig_loop = None
    asyncio.set_event_loop(io_loop.asyncio_loop)
    try:
        yield
    finally:
        if orig_loop:
            asyncio.set_event_loop(orig_loop.asyncio_loop)
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
            except Exception:  # pylint: disable=broad-except
                log.exception("Exception encountered while running stop method")
        io_loop = self.io_loop
        io_loop.stop()
        try:
            io_loop.close(all_fds=True)
        except KeyError:
            pass
        self.asyncio_loop.close()

    def __getattr__(self, key):
        if key in self._async_methods:
            return self._wrap(key)
        return getattr(self.obj, key)

    def _wrap(self, key):
        def wrap(*args, **kwargs):
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

    def _target(self, key, args, kwargs, results, asyncio_loop):
        asyncio.set_event_loop(asyncio_loop)
        io_loop = tornado.ioloop.IOLoop.current()
        try:
            result = io_loop.run_sync(lambda: getattr(self.obj, key)(*args, **kwargs))
            results.append(True)
            results.append(result)
        except Exception:  # pylint: disable=broad-except
            results.append(False)
            results.append(sys.exc_info())

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
