# coding: utf-8

# Import Python Libs
from __future__ import absolute_import

# Import 3rd-party libs
try:
    import tornado_salt.testing as tornado_testing
    import tornado_salt.gen as tornado_gen
    from tornado_salt.testing import AsyncTestCase
except ImportError:
    import tornado.testing as tornado_testing
    import tornado.gen as tornado_gen
    from tornado.testing import AsyncTestCase

from salt.utils import async


class HelperA(object):
    def __init__(self, io_loop=None):
        pass

    @tornado_gen.coroutine
    def sleep(self):
        yield tornado_gen.sleep(0.5)
        raise tornado_gen.Return(True)


class HelperB(object):
    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = async.SyncWrapper(HelperA)
        self.a = a

    @tornado_gen.coroutine
    def sleep(self):
        yield tornado_gen.sleep(0.5)
        self.a.sleep()
        raise tornado_gen.Return(False)


class TestSyncWrapper(AsyncTestCase):
    @tornado_testing.gen_test
    def test_helpers(self):
        '''
        Test that the helper classes do what we expect within a regular async env
        '''
        ha = HelperA()
        ret = yield ha.sleep()
        self.assertTrue(ret)

        hb = HelperB()
        ret = yield hb.sleep()
        self.assertFalse(ret)

    def test_basic_wrap(self):
        '''
        Test that we can wrap an async caller.
        '''
        sync = async.SyncWrapper(HelperA)
        ret = sync.sleep()
        self.assertTrue(ret)

    def test_double(self):
        '''
        Test when the async wrapper object itself creates a wrap of another thing

        This works fine since the second wrap is based on the first's IOLoop so we
        don't have to worry about complex start/stop mechanics
        '''
        sync = async.SyncWrapper(HelperB)
        ret = sync.sleep()
        self.assertFalse(ret)

    def test_double_sameloop(self):
        '''
        Test async wrappers initiated from the same IOLoop, to ensure that
        we don't wire up both to the same IOLoop (since it causes MANY problems).
        '''
        a = async.SyncWrapper(HelperA)
        sync = async.SyncWrapper(HelperB, (a,))
        ret = sync.sleep()
        self.assertFalse(ret)
