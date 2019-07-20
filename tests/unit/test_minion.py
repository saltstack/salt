# -*- coding: utf-8 -*-
'''
    :codeauthor: Mike Place <mp@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import
import copy
import os

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.helpers import skip_if_not_root
# Import salt libs
import salt.minion
import salt.utils.event as event
from salt.exceptions import SaltSystemExit, SaltMasterUnresolvableError
import salt.syspaths
from tornado.concurrent import Future
from salt.ext.six.moves import range
import tornado
import tornado.testing


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionTestCase(TestCase, AdaptedConfigurationTestCaseMixin):

    def setUp(self):
        self.opts = {}
        self.addCleanup(delattr, self, 'opts')

    def test_invalid_master_address(self):
        with patch.dict(self.opts, {'ipv6': False, 'master': float('127.0'), 'master_port': '4555', 'retry_dns': False}):
            self.assertRaises(SaltSystemExit, salt.minion.resolve_dns, self.opts)

    def test_source_int_name_local(self):
        '''
        test when file_client local and
        source_interface_name is set
        '''
        interfaces = {'bond0.1234': {'hwaddr': '01:01:01:d0:d0:d0',
                                     'up': True, 'inet':
                                     [{'broadcast': '111.1.111.255',
                                     'netmask': '111.1.0.0',
                                     'label': 'bond0',
                                     'address': '111.1.0.1'}]}}
        with patch.dict(self.opts, {'ipv6': False, 'master': '127.0.0.1',
                                   'master_port': '4555', 'file_client': 'local',
                                   'source_interface_name': 'bond0.1234',
                                   'source_ret_port': 49017,
                                   'source_publish_port': 49018}), \
            patch('salt.utils.network.interfaces',
                  MagicMock(return_value=interfaces)):
            assert salt.minion.resolve_dns(self.opts) == {'master_ip': '127.0.0.1',
                                                         'source_ip': '111.1.0.1',
                                                         'source_ret_port': 49017,
                                                         'source_publish_port': 49018,
                                                         'master_uri': 'tcp://127.0.0.1:4555'}

    def test_source_int_name_remote(self):
        '''
        test when file_client remote and
        source_interface_name is set and
        interface is down
        '''
        interfaces = {'bond0.1234': {'hwaddr': '01:01:01:d0:d0:d0',
                                     'up': False, 'inet':
                                     [{'broadcast': '111.1.111.255',
                                     'netmask': '111.1.0.0',
                                     'label': 'bond0',
                                     'address': '111.1.0.1'}]}}
        with patch.dict(self.opts, {'ipv6': False, 'master': '127.0.0.1',
                                   'master_port': '4555', 'file_client': 'remote',
                                   'source_interface_name': 'bond0.1234',
                                   'source_ret_port': 49017,
                                   'source_publish_port': 49018}), \
            patch('salt.utils.network.interfaces',
                  MagicMock(return_value=interfaces)):
            assert salt.minion.resolve_dns(self.opts) == {'master_ip': '127.0.0.1',
                                                         'source_ret_port': 49017,
                                                         'source_publish_port': 49018,
                                                         'master_uri': 'tcp://127.0.0.1:4555'}

    def test_source_address(self):
        '''
        test when source_address is set
        '''
        interfaces = {'bond0.1234': {'hwaddr': '01:01:01:d0:d0:d0',
                                     'up': False, 'inet':
                                     [{'broadcast': '111.1.111.255',
                                     'netmask': '111.1.0.0',
                                     'label': 'bond0',
                                     'address': '111.1.0.1'}]}}
        with patch.dict(self.opts, {'ipv6': False, 'master': '127.0.0.1',
                                   'master_port': '4555', 'file_client': 'local',
                                   'source_interface_name': '',
                                   'source_address': '111.1.0.1',
                                   'source_ret_port': 49017,
                                   'source_publish_port': 49018}), \
            patch('salt.utils.network.interfaces',
                  MagicMock(return_value=interfaces)):
            assert salt.minion.resolve_dns(self.opts) == {'source_publish_port': 49018,
                                                         'source_ret_port': 49017,
                                                         'master_uri': 'tcp://127.0.0.1:4555',
                                                         'source_ip': '111.1.0.1',
                                                         'master_ip': '127.0.0.1'}

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
        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
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
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
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
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
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
            mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
            mock_opts['__role'] = 'minion'
            mock_opts['minion_jid_queue_hwm'] = 100
            mock_opts["process_count_max"] = process_count_max

            io_loop = tornado.ioloop.IOLoop()
            minion = salt.minion.Minion(mock_opts, jid_queue=[], io_loop=io_loop)
            try:

                # mock gen.sleep to throw a special Exception when called, so that we detect it
                class SleepCalledException(Exception):
                    """Thrown when sleep is called"""
                    pass
                tornado.gen.sleep.return_value.set_exception(SleepCalledException())

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

                self.assertRaises(SleepCalledException,
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
            mock_opts = self.get_config('minion', from_scratch=True)
            mock_opts['beacons_before_connect'] = True
            io_loop = tornado.ioloop.IOLoop()
            io_loop.make_current()
            minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
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
            mock_opts = self.get_config('minion', from_scratch=True)
            mock_opts['scheduler_before_connect'] = True
            io_loop = tornado.ioloop.IOLoop()
            io_loop.make_current()
            minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
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

    def test_valid_ipv4_master_address_ipv6_enabled(self):
        '''
        Tests that the 'scheduler_before_connect' option causes the scheduler to be initialized before connect.
        '''
        interfaces = {'bond0.1234': {'hwaddr': '01:01:01:d0:d0:d0',
                                     'up': False, 'inet':
                                     [{'broadcast': '111.1.111.255',
                                       'netmask': '111.1.0.0',
                                       'label': 'bond0',
                                       'address': '111.1.0.1'}]}}
        with patch.dict(self.opts, {'ipv6': True, 'master': '127.0.0.1',
                                   'master_port': '4555', 'retry_dns': False,
                                   'source_address': '111.1.0.1',
                                   'source_interface_name': 'bond0.1234',
                                   'source_ret_port': 49017,
                                   'source_publish_port': 49018}), \
            patch('salt.utils.network.interfaces',
                  MagicMock(return_value=interfaces)):
            expected = {'source_publish_port': 49018,
                        'master_uri': 'tcp://127.0.0.1:4555',
                        'source_ret_port': 49017,
                        'master_ip': '127.0.0.1'}
            assert salt.minion.resolve_dns(self.opts) == expected

    def test_minion_retry_dns_count(self):
        '''
        Tests that the resolve_dns will retry dns look ups for a maximum of
        3 times before raising a SaltMasterUnresolvableError exception.
        '''
        with patch.dict(self.opts, {'ipv6': False, 'master': 'dummy',
                                   'master_port': '4555',
                                   'retry_dns': 1, 'retry_dns_count': 3}):
            self.assertRaises(SaltMasterUnresolvableError,
                              salt.minion.resolve_dns, self.opts)

    @skipIf(True, 'WAR ROOM TEMPORARY SKIP')
    def test_minion_manage_schedule(self):
        '''
        Tests that the manage_schedule will call the add function, adding
        schedule data into opts.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.minion.Minion.sync_connect_master', MagicMock(side_effect=RuntimeError('stop execution'))), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_opts = self.get_config('minion', from_scratch=True)
            io_loop = tornado.ioloop.IOLoop()
            io_loop.make_current()

            with patch('salt.utils.schedule.clean_proc_dir', MagicMock(return_value=None)):
                mock_functions = {'test.ping': None}

                minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
                minion.schedule = salt.utils.schedule.Schedule(mock_opts,
                                                               mock_functions,
                                                               returners={})

                schedule_data = {'test_job': {'function': 'test.ping',
                                              'return_job': False,
                                              'jid_include': True,
                                              'maxrunning': 2,
                                              'seconds': 10}}

                data = {'name': 'test-item',
                        'schedule': schedule_data,
                        'func': 'add'}
                tag = 'manage_schedule'

                minion.manage_schedule(tag, data)
                self.assertIn('test_job', minion.opts['schedule'])

    def test_minion_manage_beacons(self):
        '''
        Tests that the manage_beacons will call the add function, adding
        beacon data into opts.
        '''
        with patch('salt.minion.Minion.ctx', MagicMock(return_value={})), \
                patch('salt.minion.Minion.sync_connect_master', MagicMock(side_effect=RuntimeError('stop execution'))), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.start', MagicMock(return_value=True)), \
                patch('salt.utils.process.SignalHandlingMultiprocessingProcess.join', MagicMock(return_value=True)):
            mock_opts = self.get_config('minion', from_scratch=True)
            io_loop = tornado.ioloop.IOLoop()
            io_loop.make_current()

            mock_functions = {'test.ping': None}
            minion = salt.minion.Minion(mock_opts, io_loop=io_loop)
            minion.beacons = salt.beacons.Beacon(mock_opts, mock_functions)

            bdata = [{'salt-master': 'stopped'}, {'apache2': 'stopped'}]
            data = {'name': 'ps',
                    'beacon_data': bdata,
                    'func': 'add'}

            tag = 'manage_beacons'

            minion.manage_beacons(tag, data)
            self.assertIn('ps', minion.opts['beacons'])
            self.assertEqual(minion.opts['beacons']['ps'], bdata)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionAsyncTestCase(TestCase, AdaptedConfigurationTestCaseMixin, tornado.testing.AsyncTestCase):

    def setUp(self):
        super(MinionAsyncTestCase, self).setUp()
        self.opts = {}
        self.addCleanup(delattr, self, 'opts')

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
        with patch.dict(self.opts, opts):
            try:
                event_publisher = event.AsyncEventPublisher(self.opts)
                result = True
            except ValueError:
                #  There are rare cases where we operate a closed socket, especially in containers.
                # In this case, don't fail the test because we'll catch it down the road.
                result = True
            except SaltSystemExit:
                result = False
        self.assertTrue(result)

    def test_multi_master_uri_list(self):
        '''
        master_uri_list is a generated opts attr used to represent ready to feed uri's
        into salt.utils.event objects to communicate with masters. assert that it works
        '''
        _mock = MagicMock()
        future_stub = Future()
        future_stub.set_result(None)

        def dns_check(master, *args, **kwargs):
            return master

        # using context managers gets funky as ioloop callbacks reset it
        patches = [
            patch('salt.transport.client.AsyncPubChannel.factory', return_value=_mock),
            patch('salt.minion.Minion.tune_in', return_value=None),
            patch('salt.minion.Minion._post_master_init', return_value=future_stub),
            patch('salt.utils.network.dns_check', new=dns_check),
        ]
        for _patch in patches:
            _patch.start()

        mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
        mock_opts['master'] = ['master1', 'master2', 'master3']
        mock_opts['__role'] = '__minion'

        minion_manager = salt.minion.MinionManager(mock_opts)
        minion_manager.io_loop = self.io_loop
        _mock.connect.return_value = future_stub

        try:
            minion_manager._spawn_minions()

            # we just need to enter the loop to run cb's added to next iteration
            def timeout_func():
                self.io_loop.stop()

            __timeout = self.io_loop.add_timeout(self.io_loop.time() + 1, timeout_func)
            self.io_loop.start()

            self.assertTrue(len(minion_manager.minions) == 3)

            for minion in minion_manager.minions:
                self.assertEqual(minion.opts['master_uri_list'], ['tcp://master1:4506', 'tcp://master2:4506', 'tcp://master3:4506'])
        finally:
            minion_manager.destroy()

            for _patch in patches:
                _patch.stop()
