# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows IIS Module 'module.win_iis'
    :platform: Windows
    :maturity: develop
    versionadded:: Carbon
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Libs
from salt.exceptions import SaltInvocationError
from salt.modules import win_iis

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

ensure_in_syspath('../../')

# Globals
win_iis.__salt__ = {}

# Make sure this module runs on Windows system
HAS_IIS = win_iis.__virtual__()


@skipIf(not HAS_IIS, 'This test case runs only on Windows systems')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinIisTestCase(TestCase):
    '''
    Test cases for salt.modules.win_iis
    '''

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_apppools',
           MagicMock(return_value=dict()))
    def test_create_apppool(self):
        '''
        Test - Create an IIS application pool.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_apppool('MyTestPool'))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={
                     'retcode': 0,
                     'stdout': ('[{"name": "MyTestPool", "state": "Started",'
                                ' "Applications": {"value": ["MyTestSite"],'
                                ' "Count": 1}}]')}))
    def test_list_apppools(self):
        '''
        Test - List all configured IIS application pools.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertIsInstance(win_iis.list_apppools(), dict)

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_apppools',
           MagicMock(return_value={'MyTestPool': {
                                   'applications': list(),
                                   'state': 'Started'}}))
    def test_remove_apppool(self):
        '''
        Test - Remove an IIS application pool.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_apppool('MyTestPool'))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    def test_restart_apppool(self):
        '''
        Test - Restart an IIS application pool.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.restart_apppool('MyTestPool'))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_sites',
           MagicMock(return_value=dict()))
    @patch('salt.modules.win_iis.list_apppools',
           MagicMock(return_value=dict()))
    def test_create_site(self):
        '''
        Test - Create a basic website in IIS.
        '''
        kwargs = {'name': 'MyTestSite', 'sourcepath': 'C:\\inetpub\\wwwroot',
                  'apppool': 'MyTestPool', 'hostheader': 'mytestsite.local',
                  'ipaddress': '*', 'port': 80, 'protocol': 'http'}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_site(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_sites',
           MagicMock(return_value=dict()))
    @patch('salt.modules.win_iis.list_apppools',
           MagicMock(return_value=dict()))
    def test_create_site_failed(self):
        '''
        Test - Create a basic website in IIS using invalid data.
        '''
        kwargs = {'name': 'MyTestSite', 'sourcepath': 'C:\\inetpub\\wwwroot',
                  'apppool': 'MyTestPool', 'hostheader': 'mytestsite.local',
                  'ipaddress': '*', 'port': 80, 'protocol': 'invalid-protocol-name'}
        with patch.dict(win_iis.__salt__):
            self.assertRaises(SaltInvocationError, win_iis.create_site, **kwargs)


if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=C0413
    run_tests(WinIisTestCase, needs_daemon=False)
