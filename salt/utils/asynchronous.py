# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''
from __future__ import absolute_import, print_function, unicode_literals
import contextlib
import logging
import os
import sys
import threading
import traceback

import sys

import tornado.ioloop
import tornado.concurrent
import contextlib
import tornado.gen

from salt.ext.six import reraise
import salt.utils.zeromq
import salt.utils.versions

try:
    import asyncio
    from tornado.platform.asyncio import AsyncIOMainLoop
    HAS_ASYNCIO = True
except ImportError:
    HAS_ASYNCIO = False


log = logging.getLogger(__name__)


OLD_TORNADO = salt.utils.versions.LooseVersion(tornado.version) < salt.utils.versions.LooseVersion('5.0')

USES_ASYNCIO = (
    HAS_ASYNCIO and not OLD_TORNADO
)

if USES_ASYNCIO:
    # TODO: Is this really needed?
    AsyncIOMainLoop().install()
salt.utils.zeromq.install_zmq()


@contextlib.contextmanager
def current_ioloop(io_loop):
    '''
    A context manager that will set the current ioloop to io_loop for the context
    '''
    # TODO: Remove current_ioloop calls
    yield
    #orig_loop = tornado.ioloop.IOLoop.current()
    #io_loop.make_current()
    #try:
    #    yield
    #finally:
    #    orig_loop.make_current()


# TODO: Remove this.
def stack(length=4):
    return '\n'.join(traceback.format_stack()[-(length+1):-1])


class ThreadedSyncRunner(object):
    '''
    A wrapper around tornado.ioloop.IOLoop.run_sync which farms the work of
    `run_sync` out to a thread. This is to facilitate calls to `run_sync` when
    there is already an ioloop running in the current thread.
    '''

    def __init__(self, io_loop=None, lock=None):
        if io_loop is None:
            self.io_loop = tornado.ioloop.IOLoop()
        else:
            self.io_loop = io_loop
        if lock is None:
            self.lock = threading.Semaphore()
        else:
            self.lock = lock
        self._run_sync_thread = None
        self._run_sync_result = None
        self._run_sync_exc_info = None

    def _run_sync_target(self, func, timeoout=None):
        try:
            self._run_sync_result = self.io_loop.run_sync(func)
        except Exception as exc:
            # Exception is re-raised in parent thread
            self._run_sync_exc_info = sys.exc_info()

    def run_sync(self, func, timeout=None):
        with self.lock:
            self._run_sync_thread = threading.Thread(
                target=self._run_sync_target,
                args=(func,),
            )
            self._run_sync_thread.start()
            self._run_sync_thread.join()
            if self._run_sync_exc_info is None:
                result = self._run_sync_result
                self._run_sync_result = None
            else:
                reraise(*self._run_sync_exc_info)
                self._run_sync_exc_info = None
            return result


class IOLoop(object):
    '''
    A wrapper around an existing IOLoop implimentation.
    '''
    seed_loop = None

    @classmethod
    def _current(cls):
        loop = tornado.ioloop.IOLoop.current()
        if not hasattr(loop, '_salt_started_called'):
            loop._salt_started_called = False
            loop._salt_pid = os.getpid()
            loop._salt_close_called = False
        if loop._salt_pid != os.getpid() or cls._is_closed(loop):  # or loop._pid != loop._salt_pid:
            tornado.ioloop.IOLoop.clear_current()
            if not cls._is_closed(loop):
                loop.close()
            if hasattr(loop, '_impl'):
                del loop._impl
            loop = tornado.ioloop.IOLoop()
            loop._salt_started_called = False
            loop._salt_pid = os.getpid()
            loop._salt_close_called = False
        # TODO: We should not have to do this, it's happening because we're
        # instaniating the loop in a different thread thand where we start it.
        #if hasattr(loop, '_callbacks') and loop._callbacks is None:
        #    loop._callbacks = []
        return loop

    @classmethod
    def _is_closed(cls, loop):
        if hasattr(loop, '_salt_close_called'):
            if loop._salt_close_called is True:
                return True
        if hasattr(loop, '_closing'):
            if loop._closing is True:
                return True
        if hasattr(loop, 'asyncio_loop'):
            if loop.asyncio_loop.is_closed() is True:
                return True
        return False

    def __init__(self, *args, **kwargs):
        self._ioloop = kwargs.get(
            '_ioloop',
            self._current()
        )
        self.sync_runner_cls = kwargs.get(
            'sync_runner_cls',
            ThreadedSyncRunner
        )
        self.sync_runner = None

    def __getattr__(self, key):
        return getattr(self._ioloop, key)

    def add_handler(self, *args, **kwargs):
        try:
            self._ioloop.add_handler(*args, **kwargs)
        except Exception:
            reraise(*sys.exc_info())

    def start(self, *args, **kwargs):
        if not self._ioloop._salt_started_called:
            self._ioloop._salt_started_called = True
            self._ioloop.start()
        else:
            log.warn("Tried to start event loop again: %s", stack())

    def stop(self, *args, **kwargs):
        self._ioloop._salt_started_called = False
        self._ioloop.stop()

    def close(self, *args, **kwargs):
        log.debug("IOLoop.close called %s", stack())

    def real_close(self, *args, **kwargs):
        self._ioloop._salt_close_called = True
        self._ioloop.close()
        if self.sync_runner:
            self.sync_runner.io_loop.close()
            self.sync_runner = None

    def run_sync(self, func, timeout=None):
        if HAS_ASYNCIO:
            asyncio_loop = asyncio.get_event_loop()
        else:
            asyncio_loop = False
        if self.is_running() or (asyncio_loop and asyncio_loop.is_running()):
            log.debug("run_sync - with running loop")
            if self.sync_runner is None:
                self.sync_runner = self.sync_runner_cls()
            return self.sync_runner.run_sync(func)
        else:
            log.debug("run_sync - without running loop")
            return self._ioloop.run_sync(func)

    def is_running(self):
        if USES_ASYNCIO:
            try:
                return self._ioloop.is_running()
            except AttributeError:
                pass
            return self._ioloop.asyncio_loop.is_running()
        else:
            return self._ioloop._running


try:
    if IOLoop.seed_loop is None:
        IOLoop.seed_loop = IOLoop()
except AttributeError as exc:
    # When running under sphinx builds the tornaod stuff is mocked so an
    # attribute error is raised. Under normal operation this won't happen.
    log.warn('IOLoop attribute error encountered out of context')


class SyncWrapper(object):

    def __init__(self, cls, args=None, kwargs=None, async_methods=None,
            close_methods=None, loop_kwarg=None):
        self.io_loop = tornado.ioloop.IOLoop()
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
            set(async_methods + getattr(self.obj, 'async_methods', []))
        )
        self._close_methods = list(
            set(close_methods + getattr(self.obj, 'close_methods', []))
        )

    def _populate_async_methods(self):
        '''
        We need the '_coroutines' attribute on classes until we can depricate
        tornado<4.5. After that 'is_coroutine_fuction' will always be
        available.
        '''
        if hasattr(self.obj, '_coroutines'):
            self._async_methods += self.obj._coroutines

    def __repr__(self):
        return '<SyncWrapper(cls={})'.format(self.cls)

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
            except Exception:
                log.exception("Exception encountered while running stop method")
        io_loop = self.io_loop
        io_loop.stop()
        io_loop.close(all_fds=True)

    def __getattr__(self, key):
        if key in self._async_methods:
            return self._wrap(key)
        return getattr(self.obj, key)

    def _wrap(self, key):
        def wrap(*args, **kwargs):
            results = []
            thread = threading.Thread(
                target=self._target,
                args=(key, args, kwargs, results, self.io_loop),
             )
            thread.start()
            thread.join()
            if results[0]:
                return results[1]
            else:
                reraise(*results[1])
        return wrap

    def _target(self, key, args, kwargs, results, io_loop):
        try:
            result = io_loop.run_sync(
                lambda: getattr(self.obj, key)(*args, **kwargs)
            )
            results.append(True)
            results.append(result)
        except Exception as exc:
            results.append(False)
            results.append(sys.exc_info())

    def __enter__(self):
        return self

    def __exit__(self):
        self.stop()
