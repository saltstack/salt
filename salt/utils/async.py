'''
Helpers/utils for working with tornado async stuff
'''

from __future__ import absolute_import

import tornado.ioloop
import tornado.concurrent


class SyncWrapper(object):
    '''
    A wrapper to make Async classes synchronous

    This is uses as a simple wrapper, for example:

    async = AsyncClass()
    # this method would reguarly return a future
    future = async.async_method()

    sync = SyncWrapper(async)
    # the sync wrapper will automatically wait on the future
    ret = sync.async_method()
    '''
    def __init__(self, async):
        self.async = async
        self.io_loop = tornado.ioloop.IOLoop()

    def __getattribute__(self, key):
        if key in ('async', '_block_future', 'io_loop'):
            return object.__getattribute__(self, key)
        attr = getattr(self.async, key)
        if hasattr(attr, '__call__'):
            def wrap(*args, **kwargs):
                ret = attr(*args, **kwargs)
                if isinstance(ret, tornado.concurrent.Future):
                    return self._block_future(ret)
                else:
                    return ret
            return wrap

        else:
            return attr

    def _block_future(self, future):
        self.io_loop.add_future(future, lambda future: self.io_loop.stop())
        self.io_loop.start()
        return future.result()
