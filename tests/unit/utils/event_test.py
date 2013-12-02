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
from contextlib import contextmanager

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
from salt.utils import event

SOCK_DIR = os.path.join(integration.TMP, 'test-socks')

@contextmanager
def eventpublisher_process(sock_dir):
    proc = event.EventPublisher({'sock_dir':sock_dir})
    proc.start()
    try:
        time.sleep(2)
        yield
    finally:
        proc.terminate()
        proc.join()

class TestSaltEvent(TestCase):

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
        with eventpublisher_process(sock_dir=SOCK_DIR):
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe('')
            me.fire_event({'data':'foo1'}, 'evt1')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt1, {'data':'foo1'})

    def test_nested_event_subs(self):
        '''Test nested event subscriptions do not drop events, issue #8580'''
        with eventpublisher_process(sock_dir=SOCK_DIR):
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe('')
            me.fire_event({'data':'foo1'}, 'evt1')    
            me.fire_event({'data': 'foo2'}, 'evt2')
            evt2 = me.get_event(tag='evt2')
            evt1 = me.get_event(tag='evt1')
            self.assertGotEvent(evt2, {'data':'foo2'})
            self.assertGotEvent(evt1, {'data':'foo1'})

    def test_event_nodrops(self):
        '''Test a large number of events, one at a time'''
        with eventpublisher_process(sock_dir=SOCK_DIR):
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe('')
            for i in xrange(500):
                me.fire_event({'data':'{0}'.format(i)}, 'testevents')
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data':'{0}'.format(i)}, 'Event {0}'.format(i))

    def test_event_nodrop_backlog(self):
        '''Test a large number of events, send all then recv all'''
        with eventpublisher_process(sock_dir=SOCK_DIR):
            me = event.MasterEvent(sock_dir=SOCK_DIR)
            me.subscribe('')
            # Must not tp exceed zmq HWM
            for i in xrange(500):
                me.fire_event({'data':'{0}'.format(i)}, 'testevents')
            for i in xrange(500):
                evt = me.get_event(tag='testevents')
                self.assertGotEvent(evt, {'data':'{0}'.format(i)}, 'Event {0}'.format(i))




if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestSaltEvent, needs_daemon=False)
