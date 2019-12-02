# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.event_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import hashlib
import time
import warnings
from tornado.testing import AsyncTestCase
import zmq
import zmq.eventloop.ioloop
# support pyzmq 13.0.x, TODO: remove once we force people to 14.0.x
if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
    zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
from contextlib import contextmanager
from multiprocessing import Process

# Import Salt Testing libs
from tests.support.unit import expectedFailure, skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.config
import salt.utils.event
import salt.utils.stringutils
from salt.utils.process import clean_proc

# Import 3rd-+arty libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from tests.support.processes import terminate_process

SOCK_DIR = os.path.join(RUNTIME_VARS.TMP, 'test-socks')

NO_LONG_IPC = False
if getattr(zmq, 'IPC_PATH_MAX_LEN', 103) <= 103:
    NO_LONG_IPC = True


@contextmanager
def eventpublisher_process():
    proc = salt.utils.event.EventPublisher({'sock_dir': SOCK_DIR})
    proc.start()
    try:
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(2)
        yield
    finally:
        clean_proc(proc)


class EventSender(Process):
    def __init__(self, data, tag, wait):
        super(EventSender, self).__init__()
        self.data = data
        self.tag = tag
        self.wait = wait

    def run(self):
        me = salt.utils.event.MasterEvent(SOCK_DIR, listen=False)
        time.sleep(self.wait)
        me.fire_event(self.data, self.tag)
        # Wait a few seconds before tearing down the zmq context
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(2)


@contextmanager
def eventsender_process(data, tag, wait=0):
    proc = EventSender(data, tag, wait)
    proc.start()
    try:
        yield
    finally:
        clean_proc(proc)


@skipIf(NO_LONG_IPC, "This system does not support long IPC paths. Skipping event tests!")
class TestSaltEvent(TestCase):
    def setUp(self):
        if not os.path.exists(SOCK_DIR):
            os.makedirs(SOCK_DIR)

    def assertGotEvent(self, evt, data, msg=None):
        self.assertIsNotNone(evt, msg)
        for key in data:
            self.assertIn(key, evt, '{0}: Key {1} missing'.format(msg, key))
            assertMsg = '{0}: Key {1} value mismatch, {2} != {3}'
            assertMsg = assertMsg.format(msg, key, data[key], evt[key])
            self.assertEqual(data[key], evt[key], assertMsg)

    def test_master_event(self):
        me = salt.utils.event.MasterEvent(SOCK_DIR, listen=False)
        self.assertEqual(
            me.puburi, '{0}'.format(
                os.path.join(SOCK_DIR, 'master_event_pub.ipc')
            )
        )
        self.assertEqual(
            me.pulluri,
            '{0}'.format(
                os.path.join(SOCK_DIR, 'master_event_pull.ipc')
            )
        )

    def test_minion_event(self):
        opts = dict(id='foo', sock_dir=SOCK_DIR)
        id_hash = hashlib.sha256(salt.utils.stringutils.to_bytes(opts['id'])).hexdigest()[:10]
        me = salt.utils.event.MinionEvent(opts, listen=False)
        self.assertEqual(
            me.puburi,
            '{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash)
                )
            )
        )
        self.assertEqual(
            me.pulluri,
            '{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash)
                )
            )
        )

    def test_minion_event_tcp_ipc_mode(self):
        opts = dict(id='foo', ipc_mode='tcp')
        me = salt.utils.event.MinionEvent(opts, listen=False)
        self.assertEqual(me.puburi, 4510)
        self.assertEqual(me.pulluri, 4511)

    def test_minion_event_no_id(self):
        me = salt.utils.event.MinionEvent(dict(sock_dir=SOCK_DIR), listen=False)
        id_hash = hashlib.sha256(salt.utils.stringutils.to_bytes('')).hexdigest()[:10]
        self.assertEqual(
            me.puburi,
            '{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash)
                )
            )
        )
        self.assertEqual(
            me.pulluri,
            '{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash)
                )
            )
        )

    def test_event_single(self):
        '''Test a single event is received'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_single_no_block(self):
        '''Test a single event is received, no block'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            start = time.time()
            finish = start + 5
            evt1 = me.get_event(wait=0, tag='evt1', no_block=True)
            # We should get None and way before the 5 seconds wait since it's
            # non-blocking, otherwise it would wait for an event which we
            # didn't even send
            self.assertIsNone(evt1, None)
            self.assertLess(start, finish)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(wait=0, tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_single_wait_0_no_block_False(self):
        '''Test a single event is received with wait=0 and no_block=False and doesn't spin the while loop'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            # This is too fast and will be None but assures we're not blocking
            evt1 = me.get_event(wait=0, tag='evt1', no_block=False)
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_timeout(self):
        '''Test no event is received if the timeout is reached'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})
            evt2 = me.get_event(tag='evt1')
            self.assertIsNone(evt2)

    def test_event_no_timeout(self):
        '''Test no wait timeout, we should block forever, until we get one '''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            with eventsender_process({'data': 'foo2'}, 'evt2', 5):
                evt = me.get_event(tag='evt2', wait=0, no_block=False)
            self.assertGotEvent(evt, {'data': 'foo2'})

    def test_event_matching(self):
        '''Test a startswith match'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='ev')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_matching_regex(self):
        '''Test a regex match'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='^ev', match_type='regex')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_matching_all(self):
        '''Test an all match'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_matching_all_when_tag_is_None(self):
        '''Test event matching all when not passing a tag'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event()
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_not_subscribed(self):
        '''Test get_event drops non-subscribed events'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='evt2')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertIsNone(evt1)

    def test_event_subscription_cache(self):
        '''Test subscriptions cache a message until requested'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.subscribe('evt1')
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='evt2')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_subscriptions_cache_regex(self):
        '''Test regex subscriptions cache a message until requested'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.subscribe('e..1$', 'regex')
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='evt2')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_multiple_clients(self):
        '''Test event is received by multiple clients'''
        with eventpublisher_process():
            me1 = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me2 = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            # We need to sleep here to avoid a race condition wherein
            # the second socket may not be connected by the time the first socket
            # sends the event.
            time.sleep(0.5)
            me1.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me1.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})
            evt2 = me2.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data': 'foo1'})

    @expectedFailure
    def test_event_nested_sub_all(self):
        '''Test nested event subscriptions do not drop events, get event for all tags'''
        # Show why not to call get_event(tag='')
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='')
            evt1 = me.get_event(tag='')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_many(self):
        '''Test a large number of events, one at a time'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            for i in range(500):
                me.fire_event({'data': '{0}'.format(i)}, 'testevents')
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data': '{0}'.format(i)}, 'Event {0}'.format(i))

    def test_event_many_backlog(self):
        '''Test a large number of events, send all then recv all'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            # Must not exceed zmq HWM
            for i in range(500):
                me.fire_event({'data': '{0}'.format(i)}, 'testevents')
            for i in range(500):
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data': '{0}'.format(i)}, 'Event {0}'.format(i))

    # Test the fire_master function. As it wraps the underlying fire_event,
    # we don't need to perform extensive testing.
    def test_send_master_event(self):
        '''Tests that sending an event through fire_master generates expected event'''
        with eventpublisher_process():
            me = salt.utils.event.MasterEvent(SOCK_DIR, listen=True)
            data = {'data': 'foo1'}
            me.fire_master(data, 'test_master')

            evt = me.get_event(tag='fire_master')
            self.assertGotEvent(evt, {'data': data, 'tag': 'test_master', 'events': None, 'pretag': None})


class TestAsyncEventPublisher(AsyncTestCase):
    def get_new_ioloop(self):
        return zmq.eventloop.ioloop.ZMQIOLoop()

    def setUp(self):
        super(TestAsyncEventPublisher, self).setUp()
        self.opts = {'sock_dir': SOCK_DIR}
        self.publisher = salt.utils.event.AsyncEventPublisher(
            self.opts,
            self.io_loop,
        )
        self.event = salt.utils.event.get_event('minion', opts=self.opts, io_loop=self.io_loop)
        self.event.subscribe('')
        self.event.set_event_handler(self._handle_publish)

    def _handle_publish(self, raw):
        self.tag, self.data = salt.utils.event.SaltEvent.unpack(raw)
        self.stop()

    def test_event_subscription(self):
        '''Test a single event is received'''
        me = salt.utils.event.MinionEvent(self.opts, listen=True)
        me.fire_event({'data': 'foo1'}, 'evt1')
        self.wait()
        evt1 = me.get_event(tag='evt1')
        self.assertEqual(self.tag, 'evt1')
        self.data.pop('_stamp')  # drop the stamp
        self.assertEqual(self.data, {'data': 'foo1'})


class TestEventReturn(TestCase):

    def test_event_return(self):
        # Once salt is py3 only, the warnings part of this test no longer applies
        evt = None
        try:
            with warnings.catch_warnings(record=True) as w:
                # Cause all warnings to always be triggered.
                warnings.simplefilter("always")
                evt = None
                try:
                    evt = salt.utils.event.EventReturn(salt.config.DEFAULT_MASTER_OPTS.copy())
                    evt.start()
                except TypeError as exc:
                    if 'object' in str(exc):
                        self.fail('\'{}\' TypeError should have not been raised'.format(exc))
                for warning in w:
                    if warning.category is DeprecationWarning:
                        assert 'object() takes no parameters' not in warning.message
        finally:
            if evt is not None:
                terminate_process(evt.pid, kill_children=True)
