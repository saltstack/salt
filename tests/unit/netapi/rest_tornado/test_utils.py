# coding: utf-8

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import skipIf

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
from tests.unit.utils.test_event import eventpublisher_process, event, SOCK_DIR  # pylint: disable=import-error


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
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(self, 'evt1', callback=self.stop)  # get an event future
            me.fire_event({'data': 'foo2'}, 'evt2')  # fire an event we don't want
            me.fire_event({'data': 'foo1'}, 'evt1')  # fire an event we do want
            self.wait()  # wait for the future

            # check that we got the event we wanted
            self.assertTrue(event_future.done())
            self.assertEqual(event_future.result()['tag'], 'evt1')
            self.assertEqual(event_future.result()['data']['data'], 'foo1')

    def test_set_event_handler(self):
        '''
        Test subscribing events using set_event_handler
        '''
        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(self,
                                                    tag='evt',
                                                    callback=self.stop,
                                                    timeout=1,
                                                    )  # get an event future
            me.fire_event({'data': 'foo'}, 'evt')  # fire an event we do want
            self.wait()

            # check that we subscribed the event we wanted
            self.assertEqual(len(event_listener.timeout_map), 0)

    def test_timeout(self):
        '''
        Make sure timeouts work correctly
        '''
        with eventpublisher_process():
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})
            self._finished = False  # fit to event_listener's behavior
            event_future = event_listener.get_event(self,
                                                    tag='evt1',
                                                    callback=self.stop,
                                                    timeout=1,
                                                    )  # get an event future
            self.wait()
            self.assertTrue(event_future.done())
            with self.assertRaises(saltnado.TimeoutException):
                event_future.result()

    def test_clean_by_request(self):
        '''
        Make sure the method clean_by_request clean up every related data in EventListener
        request_future_1 : will be timeout-ed by clean_by_request(self)
        request_future_2 : will be finished by me.fire_event ...
        dummy_request_future_1 : will be finished by me.fire_event ...
        dummy_request_future_2 : will be timeout-ed by clean-by_request(dummy_request)
        '''
        class DummyRequest(object):
            '''
            Dummy request object to simulate the request object
            '''
            @property
            def _finished(self):
                '''
                Simulate _finished of the request object
                '''
                return False

        # Inner functions never permit modifying primitive values directly
        cnt = [0]

        def stop():
            '''
            To realize the scenario of this test, define a custom stop method to call
            self.stop after finished two events.
            '''
            cnt[0] += 1
            if cnt[0] == 2:
                self.stop()

        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_listener = saltnado.EventListener({},  # we don't use mod_opts, don't save?
                                                    {'sock_dir': SOCK_DIR,
                                                     'transport': 'zeromq'})

            self.assertEqual(0, len(event_listener.tag_map))
            self.assertEqual(0, len(event_listener.request_map))

            self._finished = False  # fit to event_listener's behavior
            dummy_request = DummyRequest()
            request_future_1 = event_listener.get_event(self, tag='evt1')
            request_future_2 = event_listener.get_event(self, tag='evt2', callback=lambda f: stop())
            dummy_request_future_1 = event_listener.get_event(dummy_request, tag='evt3', callback=lambda f: stop())
            dummy_request_future_2 = event_listener.get_event(dummy_request, timeout=10, tag='evt4')

            self.assertEqual(4, len(event_listener.tag_map))
            self.assertEqual(2, len(event_listener.request_map))

            me.fire_event({'data': 'foo2'}, 'evt2')
            me.fire_event({'data': 'foo3'}, 'evt3')
            self.wait()
            event_listener.clean_by_request(self)
            me.fire_event({'data': 'foo1'}, 'evt1')

            self.assertTrue(request_future_1.done())
            with self.assertRaises(saltnado.TimeoutException):
                request_future_1.result()

            self.assertTrue(request_future_2.done())
            self.assertEqual(request_future_2.result()['tag'], 'evt2')
            self.assertEqual(request_future_2.result()['data']['data'], 'foo2')

            self.assertTrue(dummy_request_future_1.done())
            self.assertEqual(dummy_request_future_1.result()['tag'], 'evt3')
            self.assertEqual(dummy_request_future_1.result()['data']['data'], 'foo3')

            self.assertFalse(dummy_request_future_2.done())

            self.assertEqual(2, len(event_listener.tag_map))
            self.assertEqual(1, len(event_listener.request_map))

            event_listener.clean_by_request(dummy_request)

            with self.assertRaises(saltnado.TimeoutException):
                dummy_request_future_2.result()

            self.assertEqual(0, len(event_listener.tag_map))
            self.assertEqual(0, len(event_listener.request_map))
