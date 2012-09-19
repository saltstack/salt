# -*- coding: utf-8 -*-
'''
    tests.unit.utils.event_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
'''

import os
import integration
import hashlib
from saltunittest import TestCase, TestLoader, TextTestRunner

from salt.utils import event

SOCK_DIR = os.path.join(integration.TMP, 'test-socks')

class TestSaltEvent(TestCase):

    def test_master_event(self):
        me = event.MasterEvent(SOCK_DIR)
        self.assertEqual(
            me.puburi,
            'ipc://{0}'.format(
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
                os.path.join(SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash))
            )
        )
        self.assertEqual(
            me.pulluri,
            'ipc://{0}'.format(
                os.path.join(SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash))
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
                os.path.join(SOCK_DIR, 'minion_event_{0}_pub.ipc'.format(id_hash))
            )
        )
        self.assertEqual(
            me.pulluri,
            'ipc://{0}'.format(
                os.path.join(SOCK_DIR, 'minion_event_{0}_pull.ipc'.format(id_hash))
            )
        )



if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestSaltEvent)
    TextTestRunner(verbosity=1).run(tests)
