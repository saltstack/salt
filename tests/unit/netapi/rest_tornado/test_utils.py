# coding: utf-8
import os

from salt.netapi.rest_tornado import saltnado

import tornado.testing
from salttesting import skipIf, TestCase

from unit.utils.event_test import eventpublisher_process, event, SOCK_DIR


class TestUtils(TestCase):
    def test_batching(self):
        assert 1 == saltnado.get_batch_size('1', 10)
        assert 2 == saltnado.get_batch_size('2', 10)

        assert 1 == saltnado.get_batch_size('10%', 10)
        # TODO: exception in this case? The core doesn't so we shouldn't
        assert 11 == saltnado.get_batch_size('110%', 10)


class TestEventListener(tornado.testing.AsyncTestCase):
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
            self.io_loop.add_callback(event_listener.iter_events)
            event_future = event_listener.get_event(1, 'evt1', self.stop)  # get an event future
            me.fire_event({'data': 'foo2'}, 'evt2')  # fire an event we don't want
            me.fire_event({'data': 'foo1'}, 'evt1')  # fire an event we do want
            self.wait()  # wait for the future

            # check that we got the event we wanted
            assert event_future.done()
            assert event_future.result()['tag'] ==  'evt1'
            assert event_future.result()['data']['data'] ==  'foo1'


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestUtils, needs_daemon=False)
