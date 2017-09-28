# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.modjk as modjk


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ModjkTestCase(TestCase):
    '''
    Test cases for salt.modules.modjk
    '''
    # 'version' function tests: 1

    def test_version(self):
        '''
        Test for return the modjk version
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.jk_version': 'mod_jk/1.2.37'}):
            self.assertEqual(modjk.version(), '1.2.37')

    # 'get_running' function tests: 1

    def test_get_running(self):
        '''
        Test for get the current running config (not from disk)
        '''
        with patch.object(modjk, '_do_http', return_value={}):
            self.assertDictEqual(modjk.get_running(), {})

    # 'dump_config' function tests: 1

    def test_dump_config(self):
        '''
        Test for dump the original configuration that was loaded from disk
        '''
        with patch.object(modjk, '_do_http', return_value={}):
            self.assertDictEqual(modjk.dump_config(), {})

    # 'list_configured_members' function tests: 1

    def test_list_configured_members(self):
        '''
        Test for return a list of member workers from the configuration files
        '''
        with patch.object(modjk, '_do_http', return_value={}):
            self.assertListEqual(modjk.list_configured_members('loadbalancer1'),
                                 [])

        with patch.object(modjk, '_do_http', return_value=
                          {'worker.loadbalancer1.balance_workers': 'SALT'}):
            self.assertListEqual(modjk.list_configured_members('loadbalancer1'),
                                 ['SALT'])

    # 'workers' function tests: 1

    def test_workers(self):
        '''
        Test for return a list of member workers and their status
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.list': 'Salt1,Salt2'}):
            self.assertDictEqual(modjk.workers(), {})

    # 'recover_all' function tests: 1

    def test_recover_all(self):
        '''
        Test for set the all the workers in lbn to recover and
        activate them if they are not
        '''
        with patch.object(modjk, '_do_http', return_value={}):
            self.assertDictEqual(modjk.recover_all('loadbalancer1'), {})

        with patch.object(modjk, '_do_http', return_value=
                          {'worker.loadbalancer1.balance_workers': 'SALT'}):
            with patch.object(modjk, 'worker_status',
                              return_value={'activation': 'ACT',
                                            'state': 'OK'}):
                self.assertDictEqual(modjk.recover_all('loadbalancer1'),
                                     {'SALT': {'activation': 'ACT',
                                               'state': 'OK'}})

    # 'reset_stats' function tests: 1

    def test_reset_stats(self):
        '''
        Test for reset all runtime statistics for the load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.reset_stats('loadbalancer1'))

    # 'lb_edit' function tests: 1

    def test_lb_edit(self):
        '''
        Test for edit the loadbalancer settings
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.lb_edit('loadbalancer1', {'vlr': 1,
                                                            'vlt': 60}))

    # 'bulk_stop' function tests: 1

    def test_bulk_stop(self):
        '''
        Test for stop all the given workers in the specific load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.bulk_stop(["node1", "node2", "node3"],
                                            'loadbalancer1'))

    # 'bulk_activate' function tests: 1

    def test_bulk_activate(self):
        '''
        Test for activate all the given workers in the specific load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.bulk_activate(["node1", "node2", "node3"],
                                                'loadbalancer1'))

    # 'bulk_disable' function tests: 1

    def test_bulk_disable(self):
        '''
        Test for disable all the given workers in the specific load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.bulk_disable(["node1", "node2", "node3"],
                                               'loadbalancer1'))

    # 'bulk_recover' function tests: 1

    def test_bulk_recover(self):
        '''
        Test for recover all the given workers in the specific load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.bulk_recover(["node1", "node2", "node3"],
                                               'loadbalancer1'))

    # 'worker_status' function tests: 1

    def test_worker_status(self):
        '''
        Test for return the state of the worker
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.node1.activation': 'ACT',
                           'worker.node1.state': 'OK'}):
            self.assertDictEqual(modjk.worker_status("node1"),
                                 {'activation': 'ACT', 'state': 'OK'})

        with patch.object(modjk, '_do_http', return_value={}):
            self.assertFalse(modjk.worker_status("node1"))

    # 'worker_recover' function tests: 1

    def test_worker_recover(self):
        '''
        Test for set the worker to recover this module will fail
        if it is in OK state
        '''
        with patch.object(modjk, '_do_http', return_value={}):
            self.assertDictEqual(modjk.worker_recover("node1", 'loadbalancer1'),
                                 {})

    # 'worker_disable' function tests: 1

    def test_worker_disable(self):
        '''
        Test for set the worker to disable state in the lbn load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.worker_disable('node1', 'loadbalancer1'))

    # 'worker_activate' function tests: 1

    def test_worker_activate(self):
        '''
        Test for set the worker to activate state in the lbn load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.worker_activate('node1', 'loadbalancer1'))

    # 'worker_stop' function tests: 1

    def test_worker_stop(self):
        '''
        Test for set the worker to stopped state in the lbn load balancer
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.worker_stop('node1', 'loadbalancer1'))

    # 'worker_edit' function tests: 1

    def test_worker_edit(self):
        '''
        Test for edit the worker settings
        '''
        with patch.object(modjk, '_do_http', return_value=
                          {'worker.result.type': 'OK'}):
            self.assertTrue(modjk.worker_edit('node1', 'loadbalancer1',
                                              {'vwf': 500, 'vwd': 60}))
