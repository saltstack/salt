# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Mike Place <mp@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import copy
import os

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.helpers import skip_if_not_root
# Import salt libs
import salt.minion
import salt.utils.event as event
from salt.exceptions import SaltSystemExit
import salt.syspaths
import tornado
from salt.ext.six.moves import range

__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionTestCase(TestCase):
    def test_invalid_master_address(self):
        with patch.dict(__opts__, {'ipv6': False, 'master': float('127.0'), 'master_port': '4555', 'retry_dns': False}):
            self.assertRaises(SaltSystemExit, salt.minion.resolve_dns, __opts__)

    @skip_if_not_root
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
        minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())
        try:
            ret = minion._handle_decoded_payload(mock_data).result()
            self.assertEqual(minion.jid_queue, mock_jid_queue)
            self.assertIsNone(ret)
        finally:
            minion.destroy()

    def test_handle_decoded_payload_jid_queue_addition(self):
        '''
        Tests that the _handle_decoded_payload function adds a jid to the minion's jid_queue when the new
        jid isn't already present in the jid_queue.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_jid = 11111
            mock_opts = salt.config.DEFAULT_MINION_OPTS
            mock_data = {'fun': 'foo.bar',
                         'jid': mock_jid}
            mock_jid_queue = [123, 456]
            minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())
            try:

                # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
                # This can help debug any test failures if the _handle_decoded_payload call fails.
                self.assertEqual(minion.jid_queue, mock_jid_queue)

                # Call the _handle_decoded_payload function and update the mock_jid_queue to include the new
                # mock_jid. The mock_jid should have been added to the jid_queue since the mock_jid wasn't
                # previously included. The minion's jid_queue attribute and the mock_jid_queue should be equal.
                minion._handle_decoded_payload(mock_data).result()
                mock_jid_queue.append(mock_jid)
                self.assertEqual(minion.jid_queue, mock_jid_queue)
            finally:
                minion.destroy()

    def test_handle_decoded_payload_jid_queue_reduced_minion_jid_queue_hwm(self):
        '''
        Tests that the _handle_decoded_payload function removes a jid from the minion's jid_queue when the
        minion's jid_queue high water mark (minion_jid_queue_hwm) is hit.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_opts = salt.config.DEFAULT_MINION_OPTS
            mock_opts['minion_jid_queue_hwm'] = 2
            mock_data = {'fun': 'foo.bar',
                         'jid': 789}
            mock_jid_queue = [123, 456]
            minion = salt.minion.Minion(mock_opts, jid_queue=copy.copy(mock_jid_queue), io_loop=tornado.ioloop.IOLoop())
            try:

                # Assert that the minion's jid_queue attribute matches the mock_jid_queue as a baseline
                # This can help debug any test failures if the _handle_decoded_payload call fails.
                self.assertEqual(minion.jid_queue, mock_jid_queue)

                # Call the _handle_decoded_payload function and check that the queue is smaller by one item
                # and contains the new jid
                minion._handle_decoded_payload(mock_data).result()
                self.assertEqual(len(minion.jid_queue), 2)
                self.assertEqual(minion.jid_queue, [456, 789])
            finally:
                minion.destroy()

    def test_process_count_max(self):
        '''
        Tests that the _handle_decoded_payload function does not spawn more than the configured amount of processes,
        as per process_count_max.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)), \
                patch('salt.utils.minion.running', MagicMock(return_value=[])), \
                patch('tornado.gen.sleep', MagicMock(return_value=tornado.concurrent.Future())):
            process_count_max = 10
            mock_opts = salt.config.DEFAULT_MINION_OPTS
            mock_opts['minion_jid_queue_hwm'] = 100
            mock_opts["process_count_max"] = process_count_max

            io_loop = tornado.ioloop.IOLoop()
            minion = salt.minion.Minion(mock_opts, jid_queue=[], io_loop=io_loop)
            try:

                # mock gen.sleep to throw a special Exception when called, so that we detect it
                class SleepCalledEception(Exception):
                    """Thrown when sleep is called"""
                    pass
                tornado.gen.sleep.return_value.set_exception(SleepCalledEception())

                # up until process_count_max: gen.sleep does not get called, processes are started normally
                for i in range(process_count_max):
                    mock_data = {'fun': 'foo.bar',
                                 'jid': i}
                    io_loop.run_sync(lambda data=mock_data: minion._handle_decoded_payload(data))
                    self.assertEqual(salt.utils.process.SignalHandlingMultiprocessingProcess.start.call_count, i + 1)
                    self.assertEqual(len(minion.jid_queue), i + 1)
                    salt.utils.minion.running.return_value += [i]

                # above process_count_max: gen.sleep does get called, JIDs are created but no new processes are started
                mock_data = {'fun': 'foo.bar',
                             'jid': process_count_max + 1}

                self.assertRaises(SleepCalledEception,
                                  lambda: io_loop.run_sync(lambda: minion._handle_decoded_payload(mock_data)))
                self.assertEqual(salt.utils.process.SignalHandlingMultiprocessingProcess.start.call_count,
                                 process_count_max)
                self.assertEqual(len(minion.jid_queue), process_count_max + 1)
            finally:
                minion.destroy()

    def test_beacons_before_connect(self):
        '''
        Tests that the 'beacons_before_connect' option causes the beacons to be initialized before connect.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.minion.Minion.sync_connect_master', MagicMock(side_effect=RuntimeError('stop execution'))), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_opts = copy.copy(salt.config.DEFAULT_MINION_OPTS)
            mock_opts['beacons_before_connect'] = True
            minion = salt.minion.Minion(mock_opts, io_loop=tornado.ioloop.IOLoop())
            try:

                try:
                    minion.tune_in(start=True)
                except RuntimeError:
                    pass

                # Make sure beacons are initialized but the sheduler is not
                self.assertTrue('beacons' in minion.periodic_callbacks)
                self.assertTrue('schedule' not in minion.periodic_callbacks)
            finally:
                minion.destroy()

    def test_scheduler_before_connect(self):
        '''
        Tests that the 'scheduler_before_connect' option causes the scheduler to be initialized before connect.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.minion.Minion.sync_connect_master', MagicMock(side_effect=RuntimeError('stop execution'))), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_opts = copy.copy(salt.config.DEFAULT_MINION_OPTS)
            mock_opts['scheduler_before_connect'] = True
            minion = salt.minion.Minion(mock_opts, io_loop=tornado.ioloop.IOLoop())
            try:
                try:
                    minion.tune_in(start=True)
                except RuntimeError:
                    pass

                # Make sure the scheduler is initialized but the beacons are not
                self.assertTrue('schedule' in minion.periodic_callbacks)
                self.assertTrue('beacons' not in minion.periodic_callbacks)
            finally:
                minion.destroy()
