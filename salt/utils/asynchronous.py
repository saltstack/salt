# -*- coding: utf-8 -*-
'''
Helpers/utils for working with tornado asynchronous stuff
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
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

    def __init__(self, method, args=tuple(), kwargs=None):
        if kwargs is None:
            kwargs = {}

        self.io_loop = zeromq.ZMQDefaultLoop()
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
        asynchronous = instance_dict.pop('asynchronous', None)
        if asynchronous is not None:
            # Try to close/destroy the wrapped instance.
            # This is particularly importance because iostream's or sockets
            # might need to be closed before the IOLoop is closed
            try:
                asynchronous.close()
            except AttributeError:
                # There's no close method
                try:
                    asynchronous.destroy()
                except AttributeError:
                    # There's no destroy method
                    pass

            # As a last resort, free the wrapped instance to be GC'ed
            del asynchronous

        # Close the IOLoop
        io_loop = instance_dict.pop('io_loop', None)
        if io_loop is not None:
            io_loop.close()
            del io_loop
