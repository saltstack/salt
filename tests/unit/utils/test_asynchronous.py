# coding: utf-8
from __future__ import absolute_import, print_function, unicode_literals

import salt.ext.tornado.gen
import salt.ext.tornado.testing
import salt.utils.asynchronous as asynchronous
from salt.ext.tornado.testing import AsyncTestCase
from tests.support.helpers import slowTest


class HelperA(object):
    def __init__(self, io_loop=None):
        pass

    @salt.ext.tornado.gen.coroutine
    def sleep(self):
        yield salt.ext.tornado.gen.sleep(0.5)
        raise salt.ext.tornado.gen.Return(True)


class HelperB(object):
    def __init__(self, a=None, io_loop=None):
        if a is None:
            a = asynchronous.SyncWrapper(HelperA)
        self.a = a

    @salt.ext.tornado.gen.coroutine
    def sleep(self):
        yield salt.ext.tornado.gen.sleep(0.5)
        self.a.sleep()
        raise salt.ext.tornado.gen.Return(False)


class TestSyncWrapper(AsyncTestCase):
    @salt.ext.tornado.testing.gen_test
    @slowTest
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

    @slowTest
    def test_double(self):
        """
        Test when the asynchronous wrapper object itself creates a wrap of another thing

        This works fine since the second wrap is based on the first's IOLoop so we
        don't have to worry about complex start/stop mechanics
        """
        sync = asynchronous.SyncWrapper(HelperB)
        ret = sync.sleep()
        self.assertFalse(ret)

    @slowTest
    def test_double_sameloop(self):
        """
        Test asynchronous wrappers initiated from the same IOLoop, to ensure that
        we don't wire up both to the same IOLoop (since it causes MANY problems).
        """
        a = asynchronous.SyncWrapper(HelperA)
        sync = asynchronous.SyncWrapper(HelperB, (a,))
        ret = sync.sleep()
        self.assertFalse(ret)
