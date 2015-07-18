# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado async stuff
'''

from __future__ import absolute_import

import tornado.ioloop
import tornado.concurrent
try:
    import zmq.eventloop.ioloop
    # support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
    if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
        zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
except ImportError:
    pass  # salt-ssh doesn't dep zmq

import contextlib
import weakref


class Any(tornado.concurrent.Future):
    '''
    Future that wraps other futures to "block" until one is done
    '''
    def __init__(self, futures):  # pylint: disable=E1002
        super(Any, self).__init__()
        for future in futures:
            future.add_done_callback(self.done_callback)

    def done_callback(self, future):
        # Any is completed once one is done, we don't set for the rest
        if not self.done():
            self.set_result(future)


@contextlib.contextmanager
def current_ioloop(io_loop):
    '''
    A context manager that will set the current ioloop to io_loop for the context
    '''
    orig_loop = tornado.ioloop.IOLoop.current()
    io_loop.make_current()
    try:
        yield
    finally:
        orig_loop.make_current()


class SyncWrapper(object):
    '''
    A wrapper to make Async classes synchronous

    This is uses as a simple wrapper, for example:

    async = AsyncClass()
    # this method would reguarly return a future
    future = async.async_method()

    sync = SyncWrapper(async_factory_method, (arg1, arg2), {'kwarg1': 'val'})
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
    '''
    loop_map = weakref.WeakKeyDictionary()  # keep a mapping of parent io_loop -> sync_loop

    def __init__(self, method, args=tuple(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        parent_io_loop = tornado.ioloop.IOLoop.current()
        if parent_io_loop not in SyncWrapper.loop_map:
            SyncWrapper.loop_map[parent_io_loop] = zmq.eventloop.ioloop.ZMQIOLoop()

        self.io_loop = SyncWrapper.loop_map[parent_io_loop]
        kwargs['io_loop'] = self.io_loop

        with current_ioloop(self.io_loop):
            self.async = method(*args, **kwargs)

    def __getattribute__(self, key):
        try:
            return object.__getattribute__(self, key)
        except AttributeError:
            pass
        attr = getattr(self.async, key)
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
