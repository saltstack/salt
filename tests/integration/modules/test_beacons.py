# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Justin Anderson <janderson@saltstack.com>`
'''

# Python Libs
from __future__ import absolute_import
import os

# Salt Libs
from salt.exceptions import CommandExecutionError

# Salttesting libs
import tests.integration as integration
from tests.support.unit import skipIf


class BeaconsAddDeleteTest(integration.ModuleCase):
    '''
    Tests the add and delete functions
    '''
    def setUp(self):
        self.minion_conf_d_dir = os.path.join(
                self.minion_opts['config_dir'],
                os.path.dirname(self.minion_opts['default_include']))
        if not os.path.isdir(self.minion_conf_d_dir):
            os.makedirs(self.minion_conf_d_dir)
        self.beacons_config_file_path = os.path.join(self.minion_conf_d_dir, 'beacons.conf')

    def tearDown(self):
        if os.path.isfile(self.beacons_config_file_path):
            os.unlink(self.beacons_config_file_path)

    def test_add_and_delete(self):
        '''
        Test adding and deleting a beacon
        '''
        _add = self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
        self.assertTrue(_add['result'])

        # save added beacon
        _save = self.run_function('beacons.save')
        self.assertTrue(_save['result'])

        # delete the beacon
        _delete = self.run_function('beacons.delete', ['ps'])
        self.assertTrue(_delete['result'])

        # save the results
        self.run_function('beacons.save')


class BeaconsTest(integration.ModuleCase):
    '''
    Tests the beacons execution module
    '''
    beacons_config_file_path = minion_conf_d_dir = None

    @classmethod
    def tearDownClass(cls):
        if os.path.isfile(cls.beacons_config_file_path):
            os.unlink(cls.beacons_config_file_path)

    def setUp(self):
        if self.minion_conf_d_dir is None:
            self.minion_conf_d_dir = os.path.join(
                    self.minion_opts['config_dir'],
                    os.path.dirname(self.minion_opts['default_include']))
            if not os.path.isdir(self.minion_conf_d_dir):
                os.makedirs(self.minion_conf_d_dir)
        self.__class__.beacons_config_file_path = os.path.join(self.minion_conf_d_dir, 'beacons.conf')
        try:
            # Add beacon to disable
            self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
            self.run_function('beacons.save')
        except CommandExecutionError:
            self.skipTest('Unable to add beacon')

    def tearDown(self):
        # delete added beacon
        self.run_function('beacons.delete', ['ps'])
        self.run_function('beacons.save')

    def test_disable(self):
        '''
        Test disabling beacons
        '''
        # assert beacon exists
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertIn('ps', _list)

        ret = self.run_function('beacons.disable')
        self.assertTrue(ret['result'])

        # assert beacons are disabled
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertFalse(_list['enabled'])

        # disable added beacon
        ret = self.run_function('beacons.disable_beacon', ['ps'])
        self.assertTrue(ret['result'])

        # assert beacon ps is disabled
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertFalse(_list['ps']['enabled'])

    def test_enable(self):
        '''
        Test enabling beacons
        '''
        # assert beacon exists
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertIn('ps', _list)

        # enable beacons on minion
        ret = self.run_function('beacons.enable')
        self.assertTrue(ret['result'])

        # assert beacons are enabled
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertTrue(_list['enabled'])

    @skipIf(True, 'Skip until https://github.com/saltstack/salt/issues/31516 problems are resolved.')
    def test_enabled_beacons(self):
        '''
        Test enabled specific beacon
        '''
        # enable added beacon
        ret = self.run_function('beacons.enable_beacon', ['ps'])
        self.assertTrue(ret['result'])

        # assert beacon ps is enabled
        _list = self.run_function('beacons.list', return_yaml=False)
        self.assertTrue(_list['ps']['enabled'])

    def test_list(self):
        '''
        Test lising the beacons
        '''
        # list beacons
        ret = self.run_function('beacons.list', return_yaml=False)
        if 'enabled' in ret:
            self.assertEqual(ret, {'ps': {'apache2': 'stopped'}, 'enabled': True})
        else:
            self.assertEqual(ret, {'ps': {'apache': 'stopped'}})
