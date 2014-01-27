# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.utils.event_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
import os
import hashlib
import time
import zmq
from contextlib import contextmanager
from multiprocessing import Process

# Import Salt Testing libs
from salttesting import (expectedFailure, skipIf)
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from salt.utils import event

SOCK_DIR = os.path.join(integration.TMP, 'test-socks')

NO_LONG_IPC = False
if getattr(zmq, 'IPC_PATH_MAX_LEN', 103) <= 103:
    NO_LONG_IPC = True


@contextmanager
def eventpublisher_process():
    proc = event.EventPublisher({'sock_dir': SOCK_DIR})
    proc.start()
    try:
        if os.environ.get('TRAVIS_PYTHON_VERSION', None) is not None:
            # Travis is slow
            time.sleep(10)
        else:
            time.sleep(2)
        yield
    finally:
        proc.terminate()
        proc.join()


class EventSender(Process):
    def __init__(self, data, tag, wait):
        super(EventSender, self).__init__()
        self.data = data
        self.tag = tag
        self.wait = wait

    def run(self):
        me = event.MasterEvent(sock_dir=SOCK_DIR)
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
        proc.terminate()
        proc.join()


@skipIf(NO_LONG_IPC, "This system does not support long IPC paths. Skipping event tests!")
class TestSaltEvent(TestCase):
    def setUp(self):
        if not os.path.exists(SOCK_DIR):
            os.makedirs(SOCK_DIR)

    def assertGotEvent(self, evt, data, msg=None):
        self.assertIsNotNone(evt, msg)
        for k, v in data.items():
            self.assertIn(k, evt, msg)
            self.assertEqual(data[k], evt[k], msg)

    def test_master_event(self):
        me = event.MasterEvent(SOCK_DIR)
        self.assertEqual(
            me.puburi, 'ipc://{0}'.format(
                os.path.join(SOCK_DIR, 'master_event_pub.ipc')
            )
        )
        self.assertEqual(
            me.pulluri,
            'ipc://{0}'.format(
                os.path.join(SOCK_DIR, 'master_event_pull.ipc')
            )
        )

    def test_minion_event(self):
        opts = dict(id='foo', sock_dir=SOCK_DIR)
        id_hash = hashlib.md5(opts['id']).hexdigest()
        me = event.MinionEvent(**opts)
        self.assertEqual(
            me.puburi,
            'ipc://{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash)
                )
            )
        )
        self.assertEqual(
            me.pulluri,
            'ipc://{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash)
                )
            )
        )

    def test_minion_event_tcp_ipc_mode(self):
        opts = dict(id='foo', ipc_mode='tcp')
        me = event.MinionEvent(**opts)
        self.assertEqual(me.puburi, 'tcp://127.0.0.1:4510')
        self.assertEqual(me.pulluri, 'tcp://127.0.0.1:4511')

    def test_minion_event_no_id(self):
        me = event.MinionEvent(sock_dir=SOCK_DIR)
        id_hash = hashlib.md5('').hexdigest()
        self.assertEqual(
            me.puburi,
            'ipc://{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash)
                )
            )
        )
        self.assertEqual(
            me.pulluri,
            'ipc://{0}'.format(
                os.path.join(
                    SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash)
                )
            )
        )

    def test_event_subscription(self):
        '''Test a single event is received'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_timeout(self):
        '''Test no event is received if the timeout is reached'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})
            evt2 = me.get_event(tag='evt1')
            self.assertIsNone(evt2)

    def test_event_subscription_matching(self):
        '''Test a subscription startswith matching'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_subscription_matching_all(self):
        '''Test a subscription matching'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me.get_event(tag='')
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_not_subscribed(self):
        '''Test get event ignores non-subscribed events'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            with eventsender_process({'data': 'foo1'}, 'evt1', 5):
                me.fire_event({'data': 'foo1'}, 'evt2')
                evt1 = me.get_event(tag='evt1', wait=10)
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_multiple_subscriptions(self):
        '''Test multiple subscriptions do not interfere'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            with eventsender_process({'data': 'foo1'}, 'evt1', 5):
                me.fire_event({'data': 'foo1'}, 'evt2')
                evt1 = me.get_event(tag='evt1', wait=10)
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_multiple_clients(self):
        '''Test event is received by multiple clients'''
        with eventpublisher_process():
            me1 = event.MasterEvent(sock_dir=SOCK_DIR)
            me1.subscribe()
            me2 = event.MasterEvent(sock_dir=SOCK_DIR)
            me2.subscribe()
            me1.fire_event({'data': 'foo1'}, 'evt1')
            evt1 = me1.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data': 'foo1'})
            # Can't replicate this failure int he wild, need to fix the
            # test system bug here
            #evt2 = me2.get_event(tag='evt1')
            #self.assertGotEvent(evt2, {'data': 'foo1'})

    def test_event_nested_subs(self):
        '''Test nested event subscriptions do not drop events, issue #8580'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='evt2')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertGotEvent(evt1, {'data': 'foo1'})

    @expectedFailure
    def test_event_nested_sub_all(self):
        '''Test nested event subscriptions do not drop events, get event for all tags'''
        # Show why not to call get_event(tag='')
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            me.fire_event({'data': 'foo1'}, 'evt1')
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='')
            evt1 = me.get_event(tag='')
            self.assertGotEvent(evt2, {'data': 'foo2'})
            self.assertGotEvent(evt1, {'data': 'foo1'})

    def test_event_many(self):
        '''Test a large number of events, one at a time'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            for i in xrange(500):
                me.fire_event({'data': '{0}'.format(i)}, 'testevents')
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data': '{0}'.format(i)}, 'Event {0}'.format(i))

    def test_event_many_backlog(self):
        '''Test a large number of events, send all then recv all'''
        with eventpublisher_process():
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe()
            # Must not exceed zmq HWM
            for i in xrange(500):
                me.fire_event({'data': '{0}'.format(i)}, 'testevents')
            for i in xrange(500):
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data': '{0}'.format(i)}, 'Event {0}'.format(i))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestSaltEvent, needs_daemon=False)
