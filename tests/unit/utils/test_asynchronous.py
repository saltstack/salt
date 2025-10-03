import tornado.gen
import tornado.testing
from tornado.testing import AsyncTestCase

import salt.utils.asynchronous as asynchronous


class HelperA:

    async_methods = [
        "sleep",
    ]

    def __init__(self, io_loop=None):
        pass

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        raise tornado.gen.Return(True)


class HelperB:

    async_methods = [
        "sleep",
    ]

    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = asynchronous.SyncWrapper(HelperA)
        self.a = a

    @tornado.gen.coroutine
    def sleep(self):
        yield tornado.gen.sleep(0.1)
        self.a.sleep()
        raise tornado.gen.Return(False)


class TestSyncWrapper(AsyncTestCase):
    @tornado.testing.gen_test
    def test_helpers(self):
        """
        Test that the helper classes do what we expect within a regular asynchronous env
        """
        ha = HelperA()
        ret = yield ha.sleep()
        self.assertTrue(ret)

        hb = HelperB()
        ret = yield hb.sleep()
        self.assertFalse(ret)

    def test_basic_wrap(self):
        """
        Test that we can wrap an asynchronous caller.
        """
        sync = asynchronous.SyncWrapper(HelperA)
        ret = sync.sleep()
        self.assertTrue(ret)

    def test_double(self):
        """
        Test when the asynchronous wrapper object itself creates a wrap of another thing

        This works fine since the second wrap is based on the first's IOLoop so we
        don't have to worry about complex start/stop mechanics
        """
        sync = asynchronous.SyncWrapper(HelperB)
        ret = sync.sleep()
        self.assertFalse(ret)

    def test_double_sameloop(self):
        """
        Test asynchronous wrappers initiated from the same IOLoop, to ensure that
        we don't wire up both to the same IOLoop (since it causes MANY problems).
        """
        a = asynchronous.SyncWrapper(HelperA)
        sync = asynchronous.SyncWrapper(HelperB, (a,))
        ret = sync.sleep()
        self.assertFalse(ret)
