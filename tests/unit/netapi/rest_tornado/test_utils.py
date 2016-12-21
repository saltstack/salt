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
    import tornado
    import tornado.testing
    import tornado.concurrent
    from tornado.testing import AsyncTestCase

    # To test rx in rest_tornado
    import rx.testing

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
class TestEventSubject(AsyncTestCase):
    def setUp(self):
        if not os.path.exists(SOCK_DIR):
            os.makedirs(SOCK_DIR)
        super(TestEventSubject, self).setUp()

    def test_simple(self):
        '''
        Test getting a few events
        '''
        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_subject = saltnado.EventSubject({'sock_dir': SOCK_DIR,
                                                   'transport': 'zeromq'},
                                                  )
            self._finished = False  # fit to event_listener's behavior

            result = rx.testing.TestScheduler().create_observer()

            event_subject.tag_observable_take(self, 1, tag='evt1', timeout=1) \
                         .tap(lambda _: None, lambda _: self.stop(), lambda: self.stop()) \
                         .subscribe(result)

            me.fire_event({'data': 'foo2'}, 'evt2')
            me.fire_event({'data': 'foo1'}, 'evt1')
            self.wait()

            # one for on next with data, one for on completed
            self.assertEqual(2, len(result.messages))
            self.assertEqual('evt1', result.messages[0].value.value['tag'])
            self.assertEqual('foo1', result.messages[0].value.value['data']['data'])

    def test_timeout(self):
        '''
        Make sure timeouts work correctly
        '''
        with eventpublisher_process():
            event_subject = saltnado.EventSubject({'sock_dir': SOCK_DIR,
                                                   'transport': 'zeromq'},
                                                  )
            self._finished = False  # fit to event_listener's behavior

            result = rx.testing.TestScheduler().create_observer()

            event_subject.tag_observable_take(self, 1, tag='evt1', timeout=1) \
                         .tap(lambda _: None, lambda _: self.stop(), lambda: self.stop()) \
                         .subscribe(result)

            self.wait()

            self.assertEqual(1, len(result.messages))
            with self.assertRaises(saltnado.TimeoutException):
                raise result.messages[0].value.exception

    def test_after_finished(self):
        '''
        Make sure timeouts work correctly
        '''
        with eventpublisher_process():
            me = event.MasterEvent(SOCK_DIR)
            event_subject = saltnado.EventSubject({'sock_dir': SOCK_DIR,
                                                   'transport': 'zeromq'},
                                                  )
            self._finished = True  # fit to event_listener's behavior

            result = rx.testing.TestScheduler().create_observer()

            event_subject.tag_observable_take(self, 1, tag='evt1', timeout=1) \
                         .tap(lambda _: None, lambda _: self.stop(), lambda: self.stop()) \
                         .subscribe(result)

            me.fire_event({'data': 'foo1'}, 'evt1')
            self.wait()

            self.assertEqual(1, len(result.messages))
            with self.assertRaises(saltnado.TimeoutException):
                raise result.messages[0].value.exception

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error
    run_tests(TestUtils, needs_daemon=False)
