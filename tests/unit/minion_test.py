# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import copy
import os

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock

# Import salt libs
from salt import minion
from salt.utils import event
from salt.exceptions import SaltSystemExit
import salt.syspaths
import tornado

ensure_in_syspath('../')

__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionTestCase(TestCase):
    def test_invalid_master_address(self):
        with patch.dict(__opts__, {'ipv6': False, 'master': float('127.0'), 'master_port': '4555', 'retry_dns': False}):
            self.assertRaises(SaltSystemExit, minion.resolve_dns, __opts__)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_sock_path_len(self):
        '''
        This tests whether or not a larger hash causes the sock path to exceed
        the system's max sock path length. See the below link for more
        information.

        https://github.com/saltstack/salt/issues/12172#issuecomment-43903643
        '''
        opts = {
            'id': 'salt-testing',
            'hash_type': 'sha512',
            'sock_dir': os.path.join(salt.syspaths.SOCK_DIR, 'minion'),
            'extension_modules': ''
        }
        with patch.dict(__opts__, opts):
            try:
                event_publisher = event.AsyncEventPublisher(__opts__)
                result = True
            except SaltSystemExit:
                result = False
        self.assertTrue(result)

    # Tests for _handle_decoded_payload in the salt.minion.Minion() class: 3

    def test_handle_decoded_payload_jid_match_in_jid_queue(self):
        '''
        Tests that the _handle_decoded_payload function returns when a jid is given that is already present
        in the jid_queue.

        Note: This test doesn't contain all of the patch decorators above the function like the other tests
        for _handle_decoded_payload below. This is essential to this test as the call to the function must
        return None BEFORE any of the processes are spun up because we should be avoiding firing duplicate
        jobs.
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS
        mock_data = {'fun': 'foo.bar',
                     'jid': 123}
        mock_jid_queue = [123]
        try:
            minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())
            ret = minion._handle_decoded_payload(mock_data)
            self.assertEqual(minion.jid_queue, mock_jid_queue)
            self.assertIsNone(ret)
        finally:
            minion.destroy()

    @patch('salt.minion.Minion.ctx', MagicMock(return_value={}))
    @patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True))
    @patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True))
    def test_handle_decoded_payload_jid_queue_addition(self):
        '''
        Tests that the _handle_decoded_payload function adds a jid to the minion's jid_queue when the new
        jid isn't already present in the jid_queue.
        '''
        mock_jid = 11111
        mock_opts = salt.config.DEFAULT_MINION_OPTS
        mock_data = {'fun': 'foo.bar',
                     'jid': mock_jid}
        mock_jid_queue = [123, 456]
        try:
            minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            self.assertEqual(minion.jid_queue, mock_jid_queue)

            # Call the _handle_decoded_payload function and update the mock_jid_queue to include the new
            # mock_jid. The mock_jid should have been added to the jid_queue since the mock_jid wasn't
            # previously included. The minion's jid_queue attribute and the mock_jid_queue should be equal.
            minion._handle_decoded_payload(mock_data)
            mock_jid_queue.append(mock_jid)
            self.assertEqual(minion.jid_queue, mock_jid_queue)
        finally:
            minion.destroy()

    @patch('salt.minion.Minion.ctx', MagicMock(return_value={}))
    @patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True))
    @patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True))
    def test_handle_decoded_payload_jid_queue_reduced_minion_jid_queue_hwm(self):
        '''
        Tests that the _handle_decoded_payload function removes a jid from the minion's jid_queue when the
        minion's jid_queue high water mark (minion_jid_queue_hwm) is hit.
        '''
        mock_opts = salt.config.DEFAULT_MINION_OPTS
        mock_opts['minion_jid_queue_hwm'] = 2
        mock_data = {'fun': 'foo.bar',
                     'jid': 789}
        mock_jid_queue = [123, 456]
        try:
            minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())

            # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
            # This can help debug any test failures if the _handle_decoded_payload call fails.
            self.assertEqual(minion.jid_queue, mock_jid_queue)

            # Call the _handle_decoded_payload function and check that the queue is smaller by one item
            # and contains the new jid
            minion._handle_decoded_payload(mock_data)
            self.assertEqual(len(minion.jid_queue), 2)
            self.assertEqual(minion.jid_queue, [456, 789])
        finally:
            minion.destroy()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionTestCase, needs_daemon=False)
