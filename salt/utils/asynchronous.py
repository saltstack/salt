# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import logging
import contextlib

# Import 3rd-party libs
import tornado.ioloop
import tornado.concurrent

# Import Salt libs
from salt.utils import zeromq
from salt._compat import weakref

log = logging.getLogger(__name__)


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

    asynchronous = AsyncClass()
    # this method would reguarly return a future
    future = asynchronous.async_method()

    sync = SyncWrapper(async_factory_method, (arg1, arg2), {'kwarg1': 'val'})
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
    '''

    io_loops = weakref.WeakValueDictionary()

    def __init__(self, method, args=tuple(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        pid = os.getpid()
        io_loop = SyncWrapper.io_loops.get(pid)
        if io_loop is None:
            io_loop = zeromq.ZMQDefaultLoop()
            SyncWrapper.io_loops[pid] = io_loop
            weakref.finalize(io_loop, io_loop.close, all_fds=True)
        self.io_loop = io_loop
        with current_ioloop(self.io_loop):
            self.asynchronous = method(*args, **kwargs)
        weakref.finalize(self, self.__destroy__, self.__dict__)

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

    @classmethod
    def __destroy__(cls, instance_dict):
        '''
        On deletion of the asynchronous wrapper, make sure to clean up the asynchronous stuff
        '''
        log.debug('Destroying %s instance', cls.__name__)
        asynchronous = instance_dict.get('asynchronous')
        if asynchronous is not None:
            instance_dict['asynchronous'] = None
