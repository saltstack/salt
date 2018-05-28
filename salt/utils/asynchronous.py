# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''

from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import tornado.ioloop
import tornado.concurrent
import contextlib
from salt.utils import zeromq

import logging
log = logging.getLogger(__name__)


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
                ret = attr(*args, **kwargs)
                if isinstance(ret, tornado.concurrent.Future):
                    ret = self._block_future(ret)
                return ret
            return wrap
        else:
            return attr

    def _block_future(self, future):
        io_loop = tornado.ioloop.IOLoop.current()
        io_loop.add_future(future, lambda future: io_loop.stop())
        io_loop.start()
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
            del self.asynchronous
