# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''
from __future__ import absolute_import, print_function, unicode_literals
import contextlib
import functools
import logging
import os
import sys
import threading
import time
import traceback

import sys

import tornado.ioloop
import tornado.concurrent
import contextlib
from salt.ext import six
import tornado.gen

from salt.ext.six.moves import queue
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

if HAS_ASYNCIO:
    # TODO: Is this really needed?
    AsyncIOMainLoop().install()


USES_ASYNCIO = (
    HAS_ASYNCIO and
    salt.utils.versions.LooseVersion(tornado.version) >=
    salt.utils.versions.LooseVersion('5.0')
)

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

    @classmethod
    def _current(cls):
        loop = tornado.ioloop.IOLoop.current()
        if not hasattr(loop, '_salt_started_called'):
            loop._salt_started_called = False
            loop._salt_pid = os.getpid()
        if not HAS_ASYNCIO:
            if loop._salt_pid != os.getpid():  # or loop._pid != loop._salt_pid:
                tornado.ioloop.IOLoop.clear_current()
                if hasattr(loop, '_impl'):
                    del loop._impl
                loop = tornado.ioloop.IOLoop()
                loop._salt_started_called = False
                loop._salt_pid = os.getpid()
        else:
            if loop.asyncio_loop.is_closed():
                tornado.ioloop.IOLoop.clear_current()
                loop = tornado.ioloop.IOLoop()
                loop._salt_started_called = False
                loop._salt_pid = os.getpid()
        return loop

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
        log.trace("IOLoop.close called %s", stack())
        pass

    def real_close(self, *args, **kwargs):
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
            log.trace("run_sync - with running loop")
            if self.sync_runner is None:
                self.sync_runner = self.sync_runner_cls()
            return self.sync_runner.run_sync(func)
        else:
            log.trace("run_sync - without running loop")
            return self._ioloop.run_sync(func)

    def is_running(self):
        if HAS_ASYNCIO:
            try:
                return self._ioloop.is_running()
            except AttributeError:
                pass
            return self._ioloop.asyncio_loop.is_running()
        else:
            return self._ioloop._running

class SyncWrapper(object):

    def __init__(self, cls, args=None, kwargs=None, async_methods=None,
            stop_methods=None, loop_kwarg=None):
        self.io_loop = tornado.ioloop.IOLoop()
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        if async_methods is None:
            async_methods = []
        if stop_methods is None:
            stop_methods = []
        self.args = args
        self.kwargs = kwargs
        self.loop_kwarg = loop_kwarg
        self.cls = cls
        if self.loop_kwarg:
            self.kwargs[self.loop_kwarg] = self.io_loop
        self.obj = cls(*args, **self.kwargs)
        self._async_methods = async_methods
        self._stop_methods = stop_methods
        self._populate_async_methods()

    def _populate_async_methods(self):
        '''
        We need the '_coroutines' attribute on classes until we can depricate
        tornado<4.5. After that 'is_coroutine_fuction' will always be
        available.
        '''
        if hasattr(self.obj, '_coroutines'):
            self._async_methods += self.obj._coroutines
        if hasattr(tornado.gen, 'is_coroutine_function'):
            for name in dir(self.obj):
                if tornado.gen.is_coroutine_function(getattr(self.obj, name)):
                    self._async_methods.append(name)

    def __repr__(self):
        return '<SyncWrapper(cls={})'.format(self.cls)

    def stop(self):
        for method in self._stop_methods:
            try:
                method = getattr(self, method)
            except AttributeError:
                log.error("No method %s on object %r", method, self.obj)
                continue
            try:
                method()
            except Exception:
                log.exception("Exception encountered while running stop method")
        io_loop = self.io_loop
        self.io_loop = None
        io_loop.close()
        del io_loop

    def __getattr__(self, key):
        if key in self._async_methods:
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
        return getattr(self.obj, key)

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
