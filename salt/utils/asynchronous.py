# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''

from __future__ import absolute_import, print_function, unicode_literals

import tornado.ioloop
import tornado.concurrent
import tornado.gen
import contextlib
from salt.utils import zeromq
import threading
try:
    import queue
except ImportError:
    import Queue as queue
import logging
import time
from salt.utils.zeromq import zmq, ZMQDefaultLoop, install_zmq, ZMQ_VERSION_INFO, LIBZMQ_VERSION_INFO

log = logging.getLogger(__name__)

from tornado.ioloop import IOLoop

thread_local = threading.local()

def get_ioloop():
    if not hasattr(thread_local, 'ioloop'):
        thread_local.ioloop = tornado.ioloop.IOLoop()
    return thread_local.ioloop


#@contextlib.contextmanager
#def current_ioloop(io_loop):
#    '''
#    A context manager that will set the current ioloop to io_loop for the context
#    '''
#    orig_loop = tornado.ioloop.IOLoop.current()
#    io_loop.make_current()
#    try:
#        yield
#    finally:
#        orig_loop.make_current()


@contextlib.contextmanager
def current_ioloop(io_loop):
    '''
    A context manager that will set the current ioloop to io_loop for the context
    '''
    yield

class SyncWrapper(object):
    '''
    A wrapper to make Async classes synchronous
    This is uses as a simple wrapper, for example:
    asynchronous = AsyncClass()
    # this method would reguarly return a future
    future = asynchronous.async_method()
    sync = SyncWrapper(async_factory_method, (arg1, arg2), {'kwarg1': 'val'})
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
    '''
    def __init__(self, method, args=tuple(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        self.io_loop = zeromq.ZMQDefaultLoop()
        kwargs['io_loop'] = self.io_loop

        with current_ioloop(self.io_loop):
            self.asynchronous = method(*args, **kwargs)

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError as ex:
            if key == 'asynchronous':
                raise ex
        attr = getattr(self.asynchronous, key)
        if hasattr(attr, '__call__'):
            def wrap(*args, **kwargs):
                # Overload the ioloop for the func call-- since it might call .current()
                with current_ioloop(self.io_loop):
                    ret = attr(*args, **kwargs)
                    if isinstance(ret, tornado.concurrent.Future):
                        ret = self._block_future(ret)
                    return ret
            return wrap

        else:
            return attr

    def _block_future(self, future):
        self.io_loop.add_future(future, lambda future: self.io_loop.stop())
        self.io_loop.start()
        return future.result()

    def __del__(self):
        '''
        On deletion of the asynchronous wrapper, make sure to clean up the asynchronous stuff
        '''
        if hasattr(self, 'asynchronous'):
            if hasattr(self.asynchronous, 'close'):
                # Certain things such as streams should be closed before
                # their associated io_loop is closed to allow for proper
                # cleanup.
                self.asynchronous.close()
            elif hasattr(self.asynchronous, 'destroy'):
                # Certain things such as streams should be closed before
                # their associated io_loop is closed to allow for proper
                # cleanup.
                self.asynchronous.destroy()
            del self.asynchronous
            self.io_loop.close()
            del self.io_loop
        elif hasattr(self, 'io_loop'):
            self.io_loop.close()
            del self.io_loop


class SyncThreadedWrapper(object):

    def __init__(self, cls, args=None, kwargs=None, async_methods=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        if async_methods is None:
            async_methods = []
        self.args = args
        self.kwargs = kwargs
        self.cls = cls
        self.obj = None
        self._async_methods = async_methods
        for name in dir(cls):
            if tornado.gen.is_coroutine_function(getattr(cls, name)):
                self._async_methods.append(name)
        self._req = queue.Queue()
        self._res = queue.Queue()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._target,
            args=(cls, args, kwargs, self._req, self._res, self._stop, self.stop),
        )
        self._current_future = None
        self.start()

    def __repr__(self):
        return '<SyncWrapper(cls={})'.format(self.cls)

    def start(self):
        self._thread.start()
        while self.obj is None:
            time.sleep(.01)

    def stop(self):
        if self._current_future:
            self._current_future.cancel()
        self._stop.set()
        self._thread.join()

    def __getattribute__(self, key):
        ex = None
        try:
            return object.__getattribute__(self, key)
        except AttributeError as ex:
            if key == 'obj':
                raise ex
        if key in self._async_methods:
            def wrap(*args, **kwargs):
                self._req.put((key, args, kwargs,))
                success, result = self._res.get()
                if not success:
                    raise result
                return result
            return wrap
        return getattr(self.obj, key)

    def _target(self, cls, args, kwargs, requests, responses, stop, stop_class):
        from salt.utils.zeromq import zmq, ZMQDefaultLoop, install_zmq
        tornado.ioloop.IOLoop.clear_current()
        io_loop = tornado.ioloop.IOLoop()
        io_loop.make_current()
        #install_zmq()
        #kwargs['io_loop'] = io_loop
        obj = cls(*args, **kwargs)
        for name in dir(obj):
            if tornado.gen.is_coroutine_function(getattr(obj, name)):
                self._async_methods.append(name)
        self.obj = obj
        def callback(future):
            io_loop.stop()
        io_loop.add_future(self.arg_handler(io_loop, stop, requests, responses, obj), callback)
        io_loop.start()

#    @staticmethod
    @tornado.gen.coroutine
    def arg_handler(self, io_loop, stop, requests, responses, obj):
        while not stop.is_set():
            try:
                attr_name, call_args, call_kwargs = requests.get(block=False)
            except queue.Empty:
                yield tornado.gen.sleep(.01)
            else:
                attr = getattr(obj, attr_name)
                ret = attr(*call_args, **call_kwargs)
                def callback(future):
                    self._current_future = None
                    res = future.result()
                    responses.put((True, res,))
                io_loop.add_future(ret, callback)
                self._current_future = ret
                yield
        raise tornado.gen.Return(True)


SyncWrapper = SyncThreadedWrapper


def run_sync_threaded(func, args=None, kwargs=None):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    results = {}
    def runner():
        from salt.utils.zeromq import zmq, ZMQDefaultLoop, install_zmq
        tornado.ioloop.IOLoop.clear_current()
        io_loop = tornado.ioloop.IOLoop()
        io_loop.make_current()
        ret = func(*args, **kwargs)
        if isinstance(ret, tornado.concurrent.Future):
            io_loop.add_future(ret, lambda future: io_loop.stop())
            io_loop.start()
            exc = ret.exception()
            if exc:
                results['exc'] = exc
            else:
                results['ret'] = ret.result()
        else:
            results['ret'] = ret
    t = threading.Thread(target=runner)
    t.start()
    t.join()
    if 'exc' in results:
        raise results['exc']
    return results['ret']
