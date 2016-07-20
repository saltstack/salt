# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import kmod


class KmodTestCase(TestCase):
    '''
    TestCase for salt.modules.kmod
    '''
    kmod.__grains__ = {}
    kmod.__salt__ = {}
    kmod.__context__ = {}

    # 'available' function tests: 1

    @patch('salt.modules.kmod.available', MagicMock(return_value=['kvm']))
    def test_available(self):
        '''
        Tests return a list of all available kernel modules
        '''
        self.assertEqual(['kvm'], kmod.available())

    # 'check_available' function tests: 1

    @patch('salt.modules.kmod.available', MagicMock(return_value=['kvm']))
    def test_check_available(self):
        '''
        Tests if the specified kernel module is available
        '''
        self.assertTrue(kmod.check_available('kvm'))

    # 'lsmod' function tests: 1

    def test_lsmod(self):
        '''
        Tests return information about currently loaded modules
        '''
        mock_ret = [{'size': 100, 'module': None, 'depcount': 10, 'deps': None}]
        with patch('salt.modules.kmod.lsmod', MagicMock(return_value=mock_ret)):
            mock_cmd = MagicMock(return_value=1)
            with patch.dict(kmod.__salt__, {'cmd.run': mock_cmd}):
                self.assertListEqual(mock_ret, kmod.lsmod())

    # 'mod_list' function tests: 1

    @skipIf(not os.path.isfile('/etc/modules'), '/etc/modules not present')
    def test_mod_list(self):
        '''
        Tests return a list of the loaded module names
        '''
        with patch('salt.modules.kmod._get_modules_conf',
                   MagicMock(return_value='/etc/modules')):
            with patch('salt.modules.kmod._strip_module_name',
                       MagicMock(return_value='lp')):
                self.assertListEqual(['lp'], kmod.mod_list(True))

        mock_ret = [{'size': 100, 'module': None, 'depcount': 10, 'deps': None}]
        with patch('salt.modules.kmod.lsmod', MagicMock(return_value=mock_ret)):
            self.assertListEqual([None], kmod.mod_list(False))

    # 'load' function tests: 1

    @patch('salt.modules.kmod._set_persistent_module',
           MagicMock(return_value=set(['lp'])))
    def test_load(self):
        '''
        Tests to loads specified kernel module.
        '''
        mock_ret = [{'size': 100, 'module': None, 'depcount': 10, 'deps': None}]
        with patch('salt.modules.kmod.lsmod', MagicMock(return_value=mock_ret)):
            mock = MagicMock(return_value={'retcode': 0})
            with patch.dict(kmod.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(['lp'], kmod.load('lp', True))

            mock = MagicMock(return_value={'retcode': 1})
            with patch.dict(kmod.__salt__, {'cmd.run_all': mock}):
                self.assertEqual('Module abc not found', kmod.load('abc'))

    # 'is_loaded' function tests: 1

    @patch('salt.modules.kmod.mod_list', MagicMock(return_value=set(['lp'])))
    def test_is_loaded(self):
        '''
        Tests if specified kernel module is loaded.
        '''
        self.assertTrue(kmod.is_loaded('lp'))

    # 'remove' function tests: 1

    @patch('salt.modules.kmod._remove_persistent_module',
           MagicMock(return_value=set(['lp'])))
    def test_remove(self):
        '''
        Tests to remove the specified kernel module
        '''
        mock_ret = [{'size': 100, 'module': None, 'depcount': 10, 'deps': None}]
        with patch('salt.modules.kmod.lsmod', MagicMock(return_value=mock_ret)):
            mock = MagicMock(return_value=0)
            with patch.dict(kmod.__salt__, {'cmd.run_all': mock}):
                self.assertEqual(['lp'], kmod.remove('lp', True))

                self.assertEqual([], kmod.remove('lp'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(KmodTestCase, needs_daemon=False)
