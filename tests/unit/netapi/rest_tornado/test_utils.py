# coding: utf-8

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting.unit import skipIf
from salttesting.case import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../..')

# Import 3rd-party libs
# pylint: disable=import-error
try:
    import tornado.testing
    import tornado.concurrent
    from tornado.testing import AsyncTestCase
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

    # Let's create a fake AsyncHTTPTestCase so we can properly skip the test case
    class AsyncTestCase(object):
        pass

from salt.ext.six.moves import range  # pylint: disable=redefined-builtin
# pylint: enable=import-error

try:
    from salt.netapi.rest_tornado import saltnado
    HAS_TORNADO = True
except ImportError:
    HAS_TORNADO = False

# Import utility lib from tests
from unit.utils.event_test import eventpublisher_process, event, SOCK_DIR  # pylint: disable=import-error


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')
class TestUtils(TestCase):
    def test_batching(self):
        self.assertEqual(1, saltnado.get_batch_size('1', 10))
        self.assertEqual(2, saltnado.get_batch_size('2', 10))

        self.assertEqual(1, saltnado.get_batch_size('10%', 10))
        # TODO: exception in this case? The core doesn't so we shouldn't
        self.assertEqual(11, saltnado.get_batch_size('110%', 10))


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')
class TestSaltnadoUtils(AsyncTestCase):
    def test_any_future(self):
        '''
        Test that the Any Future does what we think it does
        '''
        # create a few futures
        futures = []
        for x in range(0, 3):
            future = tornado.concurrent.Future()
            future.add_done_callback(self.stop)
            futures.append(future)

        # create an any future, make sure it isn't immediately done
        any_ = saltnado.Any(futures)
        self.assertIs(any_.done(), False)

        # finish one, lets see who finishes
        futures[0].set_result('foo')
        self.wait()

        self.assertIs(any_.done(), True)
        self.assertIs(futures[0].done(), True)
        self.assertIs(futures[1].done(), False)
        self.assertIs(futures[2].done(), False)

        # make sure it returned the one that finished
        self.assertEqual(any_.result(), futures[0])

        futures = futures[1:]
        # re-wait on some other futures
        any_ = saltnado.Any(futures)
        futures[0].set_result('foo')
        self.wait()
        self.assertIs(any_.done(), True)
        self.assertIs(futures[0].done(), True)
        self.assertIs(futures[1].done(), False)


@skipIf(HAS_TORNADO is False, 'The tornado package needs to be installed')
class TestEventListener(AsyncTestCase):
    def setUp(self):
        if not os.path.exists(SOCK_DIR):
            os.makedirs(SOCK_DIR)
        super(TestEventListener, self).setUp()

    def test_simple(self):
        '''
        Test getting a few events
        '''
        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})
            event_future = event_listener.get_event(1, 'evt1', self.stop)  # get an event future
            me.fire_event({'data': 'foo2'}, 'evt2')  # fire an event we don't want
            me.fire_event({'data': 'foo1'}, 'evt1')  # fire an event we do want
            self.wait()  # wait for the future

            # check that we got the event we wanted
            self.assertTrue(event_future.done())
            self.assertEqual(event_future.result()['tag'], 'evt1')
            self.assertEqual(event_future.result()['data']['data'], 'foo1')

    def test_timeout(self):
        '''
        Make sure timeouts work correctly
        '''
        with eventpublisher_process():
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})
            event_future = event_listener.get_event(1,
                                                    tag='evt1',
                                                    callback=self.stop,
                                                    timeout=1,
                                                    )  # get an event future
            self.wait()
            self.assertTrue(event_future.done())
            with self.assertRaises(saltnado.TimeoutException):
                event_future.result()

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(TestUtils, needs_daemon=False)
