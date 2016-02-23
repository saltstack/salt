# -*- coding: utf-8 -*-

# Python Libs
from __future__ import absolute_import
import os

# Salt Libs
from salt.modules import beacons
from salt.exceptions import CommandExecutionError
import integration

# Salttesting libs
from salttesting import skipIf
from salttesting.helpers import destructiveTest, ensure_in_syspath

ensure_in_syspath('../../')

beacons.__opts__ = {}

BEACON_CONF_DIR = os.path.join(integration.TMP, 'minion.d')
if not os.path.exists(BEACON_CONF_DIR):
    os.makedirs(BEACON_CONF_DIR)

@destructiveTest
@skipIf(os.geteuid() != 0, 'You must be root to run these tests')
class BeaconsTest(integration.ModuleCase):
    '''
    Tests the beacons execution module
    '''
    def test_add(self):
        '''
        Test adding a beacon
        '''
        _add = self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
        self.assertTrue(_add['result'])

        # save added beacon
        _save = self.run_function('beacons.save')
        self.assertTrue(_save['result'])

    def test_delete(self):
        '''
        Test deleting a beacon
        '''
        _delete = self.run_function('beacons.delete', ['ps'])
        self.assertTrue(_delete['result'])

        # save the results
        self.run_function('beacons.save')

    def test_disable(self):
        '''
        Test disabling beacons
        '''
        try:
            # Add beacon to disable
            self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
            self.run_function('beacons.save')
        except CommandExecutionError:
            self.skipTest('Unable to add beacon')

        # disable beacons on minion
        ret = self.run_function('beacons.disable')
        self.assertTrue(ret['result'])
        # disable added beacon
        ret = self.run_function('beacons.disable_beacon', ['ps'])
        self.assertTrue(ret['result'])

        # delete added beacon
        self.run_function('beacons.delete', ['ps'])
        self.run_function('beacons.save')

    def test_enable(self):
        '''
        Test enabling beacons
        '''
        try:
            # Add beacon to enable
            self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
            self.run_function('beacons.save')
        except CommandExecutionError:
            self.skipTest('Unable to add beacon')

        # enable beacons on minion
        ret = self.run_function('beacons.enable')
        self.assertTrue(ret['result'])
        # enable added beacon
        ret = self.run_function('beacons.enable_beacon', ['ps'])
        self.assertTrue(ret['result'])

        # delete added beacon
        self.run_function('beacons.delete', ['ps'])
        self.run_function('beacons.save')

    def test_list(self):
        '''
        Test lising the beacons
        '''
        try:
            # Add beacon to list
            self.run_function('beacons.add', ['ps', {'apache2': 'stopped'}])
            self.run_function('beacons.save')
        except CommandExecutionError:
            self.skipTest('Unable to add beacon')

        # list beacons
        ret = self.run_function('beacons.list', return_yaml=False)
        if 'enabled' in ret:
            self.assertEqual(ret, {'ps': {'apache2': 'stopped'}, 'enabled': True})
        else:
            self.assertEqual(ret, {'ps': {'apache': 'stopped'}})

        # delete added beacon
        self.run_function('beacons.delete', ['ps'])
        self.run_function('beacons.save')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(BeaconsTest)
