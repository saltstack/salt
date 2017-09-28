# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch

# Import Salt Libs
import salt.modules.kmod as kmod


class KmodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.kmod
    '''

    def setup_loader_modules(self):
        return {kmod: {}}

    # 'available' function tests: 1

    def test_available(self):
        '''
        Tests return a list of all available kernel modules
        '''
        with patch('salt.modules.kmod.available', MagicMock(return_value=['kvm'])):
            self.assertEqual(['kvm'], kmod.available())

    # 'check_available' function tests: 1

    def test_check_available(self):
        '''
        Tests if the specified kernel module is available
        '''
        with patch('salt.modules.kmod.available', MagicMock(return_value=['kvm'])):
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

    def test_load(self):
        '''
        Tests to loads specified kernel module.
        '''
        mod = 'cheese'
        err_msg = 'Module too moldy, refusing to load'
        mock_persist = MagicMock(return_value=set([mod]))
        mock_lsmod = MagicMock(return_value=[{'size': 100,
                                              'module': None,
                                              'depcount': 10,
                                              'deps': None}])
        mock_run_all_0 = MagicMock(return_value={'retcode': 0})
        mock_run_all_1 = MagicMock(return_value={'retcode': 1,
                                                 'stderr': err_msg})

        with patch('salt.modules.kmod._set_persistent_module', mock_persist):
            with patch('salt.modules.kmod.lsmod', mock_lsmod):
                with patch.dict(kmod.__salt__, {'cmd.run_all': mock_run_all_0}):
                    self.assertEqual([mod], kmod.load(mod, True))

                with patch.dict(kmod.__salt__, {'cmd.run_all': mock_run_all_1}):
                    self.assertEqual('Error loading module {0}: {1}'.format(mod, err_msg),
                                     kmod.load(mod))

    # 'is_loaded' function tests: 1

    def test_is_loaded(self):
        '''
        Tests if specified kernel module is loaded.
        '''
        with patch('salt.modules.kmod.mod_list', MagicMock(return_value=set(['lp']))):
            self.assertTrue(kmod.is_loaded('lp'))

    # 'remove' function tests: 1

    def test_remove(self):
        '''
        Tests to remove the specified kernel module
        '''
        mod = 'cheese'
        err_msg = 'Cannot find module: it has been eaten'
        mock_persist = MagicMock(return_value=set([mod]))
        mock_lsmod = MagicMock(return_value=[{'size': 100,
                                              'module': None,
                                              'depcount': 10,
                                              'deps': None}])
        mock_run_all_0 = MagicMock(return_value={'retcode': 0})
        mock_run_all_1 = MagicMock(return_value={'retcode': 1,
                                                 'stderr': err_msg})

        with patch('salt.modules.kmod._remove_persistent_module', mock_persist):
            with patch('salt.modules.kmod.lsmod', mock_lsmod):
                with patch.dict(kmod.__salt__, {'cmd.run_all': mock_run_all_0}):
                    self.assertEqual([mod], kmod.remove(mod, True))

                    self.assertEqual([], kmod.remove(mod))

                with patch.dict(kmod.__salt__, {'cmd.run_all': mock_run_all_1}):
                    self.assertEqual('Error removing module {0}: {1}'.format(mod, err_msg),
                                     kmod.remove(mod, True))
