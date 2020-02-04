# -*- coding: utf-8 -*-
'''
    :codeauthor: Justin Anderson <janderson@saltstack.com>
'''

# Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Salt Libs
from salt.exceptions import CommandExecutionError

# Salttesting libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


class BeaconsAddDeleteTest(ModuleCase):
    '''
    Tests the add and delete functions
    '''
    def setUp(self):
        self.minion_conf_d_dir = os.path.join(
                RUNTIME_VARS.TMP_CONF_DIR,
                os.path.dirname(self.minion_opts['default_include']))
        if not os.path.isdir(self.minion_conf_d_dir):
            os.makedirs(self.minion_conf_d_dir)
        self.beacons_config_file_path = os.path.join(self.minion_conf_d_dir, 'beacons.conf')

    def tearDown(self):
        if os.path.isfile(self.beacons_config_file_path):
            os.unlink(self.beacons_config_file_path)

        # Reset beacons
        self.run_function('beacons.reset', f_timeout=300)

    def test_add_and_delete(self):
        '''
        Test adding and deleting a beacon
        '''
        _add = self.run_function(
            'beacons.add',
            ['ps', [{'processes': {'apache2': 'stopped'}}]],
            f_timeout=300
        )
        self.assertTrue(_add['result'])

        # save added beacon
        _save = self.run_function('beacons.save', f_timeout=300)
        self.assertTrue(_save['result'])

        # delete the beacon
        _delete = self.run_function('beacons.delete', ['ps'], f_timeout=300)
        self.assertTrue(_delete['result'])

        # save the results
        self.run_function('beacons.save', f_timeout=300)


class BeaconsTest(ModuleCase):
    '''
    Tests the beacons execution module
    '''
    beacons_config_file_path = minion_conf_d_dir = None

    @classmethod
    def tearDownClass(cls):
        if cls.beacons_config_file_path and os.path.isfile(cls.beacons_config_file_path):
            os.unlink(cls.beacons_config_file_path)

    def setUp(self):
        if self.minion_conf_d_dir is None:
            self.minion_conf_d_dir = os.path.join(
                    RUNTIME_VARS.TMP_CONF_DIR,
                    os.path.dirname(self.minion_opts['default_include']))
            if not os.path.isdir(self.minion_conf_d_dir):
                os.makedirs(self.minion_conf_d_dir)
        self.__class__.beacons_config_file_path = os.path.join(self.minion_conf_d_dir, 'beacons.conf')
        try:
            # Add beacon to disable
            self.run_function('beacons.add',
                              ['ps', [{'processes': {'apache2': 'stopped'}}]],
                              f_timeout=300)
            self.run_function('beacons.save', f_timeout=300)
        except CommandExecutionError:
            self.skipTest('Unable to add beacon')

    def tearDown(self):
        # delete added beacon
        self.run_function('beacons.delete', ['ps'], f_timeout=300)
        self.run_function('beacons.save', f_timeout=300)

        # Reset beacons
        self.run_function('beacons.reset', f_timeout=300)

    def test_disable(self):
        '''
        Test disabling beacons
        '''
        # assert beacon exists
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        self.assertIn('ps', _list)

        ret = self.run_function('beacons.disable', f_timeout=300)
        self.assertTrue(ret['result'])

        # assert beacons are disabled
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        self.assertFalse(_list['enabled'])

        # disable added beacon
        ret = self.run_function('beacons.disable_beacon', ['ps'], f_timeout=300)
        self.assertTrue(ret['result'])

        # assert beacon ps is disabled
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        for bdict in _list['ps']:
            if 'enabled' in bdict:
                self.assertFalse(bdict['enabled'])
                break

    def test_enable(self):
        '''
        Test enabling beacons
        '''
        # assert beacon exists
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        self.assertIn('ps', _list)

        # enable beacons on minion
        ret = self.run_function('beacons.enable', f_timeout=300)
        self.assertTrue(ret['result'])

        # assert beacons are enabled
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        self.assertTrue(_list['enabled'])

    @skipIf(True, 'Skip until https://github.com/saltstack/salt/issues/31516 '
                  'problems are resolved.')
    def test_enabled_beacons(self):
        '''
        Test enabled specific beacon
        '''
        # enable added beacon
        ret = self.run_function('beacons.enable_beacon', ['ps'], f_timeout=300)
        self.assertTrue(ret['result'])

        # assert beacon ps is enabled
        _list = self.run_function('beacons.list',
                                  return_yaml=False,
                                  f_timeout=300)
        self.assertTrue(_list['ps']['enabled'])

    def test_list(self):
        '''
        Test listing the beacons
        '''
        # list beacons
        ret = self.run_function('beacons.list',
                                return_yaml=False,
                                f_timeout=300)
        if 'enabled' in ret:
            self.assertEqual(ret, {'ps': [{'processes': {'apache2': 'stopped'}}], 'enabled': True})
        else:
            self.assertEqual(ret, {'ps': [{'processes': {'apache2': 'stopped'}}]})

    def test_list_available(self):
        '''
        Test listing the beacons
        '''
        # list beacons
        ret = self.run_function('beacons.list_available',
                                return_yaml=False,
                                f_timeout=300)
        self.assertTrue(ret)
