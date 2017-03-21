# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows IIS Module 'module.win_iis'
    :platform: Windows
    :maturity: develop
    versionadded:: 2016.11.0
'''

# Import Python Libs
from __future__ import absolute_import
import json

# Import Salt Libs
from salt.exceptions import SaltInvocationError
import salt.modules.win_iis as win_iis

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Globals
win_iis.__salt__ = {}

# Make sure this module runs on Windows system
HAS_IIS = win_iis.__virtual__()

APP_LIST = {
    'testApp': {
        'apppool': 'MyTestPool',
        'path': '/testApp',
        'preload': False,
        'protocols': ['http'],
        'sourcepath': r'C:\inetpub\apps\testApp'
    }
}

APPPOOL_LIST = {
    'MyTestPool': {
        'applications': ['MyTestSite'],
        'state': 'Started'
    }
}

BINDING_LIST = {
    '*:80:': {
        'certificatehash': None,
        'certificatestorename': None,
        'hostheader': None,
        'ipaddress': '*', 'port': 80,
        'protocol': 'http',
        'sslflags': 0
    },
    '*:443:mytestsite.local': {
        'certificatehash': '9988776655443322111000AAABBBCCCDDDEEEFFF',
        'certificatestorename': 'My',
        'hostheader': 'mytestsite.local',
        'ipaddress': '*',
        'port': 443,
        'protocol': 'https',
        'sslflags': 0
    }
}

SITE_LIST = {
    'MyTestSite': {
        'apppool': 'MyTestPool',
        'bindings': BINDING_LIST,
        'id': 1, 'sourcepath': r'C:\inetpub\wwwroot',
        'state': 'Started'
    }
}

VDIR_LIST = {
    'TestVdir': {
        'sourcepath': r'C:\inetpub\vdirs\TestVdir'
    }
}

LIST_APPS_SRVMGR = {
    'retcode': 0,
    'stdout': json.dumps([{
        'applicationPool': 'MyTestPool',
        'name': 'testApp', 'path': '/testApp',
        'PhysicalPath': r'C:\inetpub\apps\testApp',
        'preloadEnabled': False,
        'protocols': 'http'
    }])
}

LIST_APPPOOLS_SRVMGR = {
    'retcode': 0,
    'stdout': json.dumps([{
        'name': 'MyTestPool', 'state': 'Started',
        'Applications': {
            'value': ['MyTestSite'],
            'Count': 1
        }
    }])
}

LIST_VDIRS_SRVMGR = {
    'retcode': 0,
    'stdout': json.dumps([{
        'name': 'TestVdir',
        'physicalPath': r'C:\inetpub\vdirs\TestVdir'
    }])
}

CONTAINER_SETTING = {
    'retcode': 0,
    'stdout': json.dumps([{
        'managedPipelineMode': 'Integrated'
    }])
}

CERT_BINDING_INFO = '*:443:mytestsite.local'


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
           MagicMock(return_value=LIST_APPPOOLS_SRVMGR))
    def test_list_apppools(self):
        '''
        Test - List all configured IIS application pools.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.list_apppools(), APPPOOL_LIST)

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
        kwargs = {'name': 'MyTestSite', 'sourcepath': r'C:\inetpub\wwwroot',
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
        kwargs = {'name': 'MyTestSite', 'sourcepath': r'C:\inetpub\wwwroot',
                  'apppool': 'MyTestPool', 'hostheader': 'mytestsite.local',
                  'ipaddress': '*', 'port': 80, 'protocol': 'invalid-protocol-name'}
        with patch.dict(win_iis.__salt__):
            self.assertRaises(SaltInvocationError, win_iis.create_site, **kwargs)

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_sites',
           MagicMock(return_value=SITE_LIST))
    def test_remove_site(self):
        '''
        Test - Delete a website from IIS.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_site('MyTestSite'))

    @patch('os.path.isdir',
           MagicMock(return_value=True))
    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_apps',
           MagicMock(return_value=APP_LIST))
    def test_create_app(self):
        '''
        Test - Create an IIS application.
        '''
        kwargs = {'name': 'testApp', 'site': 'MyTestSite',
                  'sourcepath': r'C:\inetpub\apps\testApp', 'apppool': 'MyTestPool'}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_app(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value=LIST_APPS_SRVMGR))
    def test_list_apps(self):
        '''
        Test - Get all configured IIS applications for the specified site.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.list_apps('MyTestSite'), APP_LIST)

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_apps',
           MagicMock(return_value=APP_LIST))
    def test_remove_app(self):
        '''
        Test - Remove an IIS application.
        '''
        kwargs = {'name': 'otherApp', 'site': 'MyTestSite'}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_app(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_bindings',
           MagicMock(return_value=BINDING_LIST))
    def test_create_binding(self):
        '''
        Test - Create an IIS binding.
        '''
        kwargs = {'site': 'MyTestSite', 'hostheader': '', 'ipaddress': '*',
                  'port': 80, 'protocol': 'http', 'sslflags': 0}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_binding(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_bindings',
           MagicMock(return_value=BINDING_LIST))
    def test_create_binding_failed(self):
        '''
        Test - Create an IIS binding using invalid data.
        '''
        kwargs = {'site': 'MyTestSite', 'hostheader': '', 'ipaddress': '*',
                  'port': 80, 'protocol': 'invalid-protocol-name', 'sslflags': 999}
        with patch.dict(win_iis.__salt__):
            self.assertRaises(SaltInvocationError, win_iis.create_binding, **kwargs)

    @patch('salt.modules.win_iis.list_sites',
           MagicMock(return_value=SITE_LIST))
    def test_list_bindings(self):
        '''
        Test - Get all configured IIS bindings for the specified site.
        '''
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.list_bindings('MyTestSite'), BINDING_LIST)

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_bindings',
           MagicMock(return_value=BINDING_LIST))
    def test_remove_binding(self):
        '''
        Test - Remove an IIS binding.
        '''
        kwargs = {'site': 'MyTestSite', 'hostheader': 'myothertestsite.local',
                  'ipaddress': '*', 'port': 443}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_binding(**kwargs))

    @patch('os.path.isdir',
           MagicMock(return_value=True))
    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_vdirs',
           MagicMock(return_value=VDIR_LIST))
    def test_create_vdir(self):
        '''
        Test - Create an IIS virtual directory.
        '''
        kwargs = {'name': 'TestVdir', 'site': 'MyTestSite',
                  'sourcepath': r'C:\inetpub\vdirs\TestVdir'}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_vdir(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value=LIST_VDIRS_SRVMGR))
    def test_list_vdirs(self):
        '''
        Test - Get configured IIS virtual directories.
        '''
        vdirs = {
            'TestVdir': {
                'sourcepath': r'C:\inetpub\vdirs\TestVdir'
            }
        }
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.list_vdirs('MyTestSite'), vdirs)

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_vdirs',
           MagicMock(return_value=VDIR_LIST))
    def test_remove_vdir(self):
        '''
        Test - Remove an IIS virtual directory.
        '''
        kwargs = {'name': 'TestOtherVdir', 'site': 'MyTestSite'}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_vdir(**kwargs))

    @patch('salt.modules.win_iis._list_certs',
           MagicMock(return_value={'9988776655443322111000AAABBBCCCDDDEEEFFF': None}))
    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0, 'stdout': 10}))
    @patch('json.loads', MagicMock(return_value=[{'MajorVersion': 10, 'MinorVersion': 0}]))
    @patch('salt.modules.win_iis.list_bindings',
           MagicMock(return_value=BINDING_LIST))
    @patch('salt.modules.win_iis.list_cert_bindings',
           MagicMock(return_value={CERT_BINDING_INFO: BINDING_LIST[CERT_BINDING_INFO]}))
    def test_create_cert_binding(self):
        '''
        Test - Assign a certificate to an IIS binding.
        '''
        kwargs = {'name': '9988776655443322111000AAABBBCCCDDDEEEFFF',
                  'site': 'MyTestSite', 'hostheader': 'mytestsite.local',
                  'ipaddress': '*', 'port': 443}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.create_cert_binding(**kwargs))

    @patch('salt.modules.win_iis.list_sites',
           MagicMock(return_value=SITE_LIST))
    def test_list_cert_bindings(self):
        '''
        Test - List certificate bindings for an IIS site.
        '''
        key = '*:443:mytestsite.local'
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.list_cert_bindings('MyTestSite'),
                             {key: BINDING_LIST[key]})

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.list_cert_bindings',
           MagicMock(return_value={CERT_BINDING_INFO: BINDING_LIST[CERT_BINDING_INFO]}))
    def test_remove_cert_binding(self):
        '''
        Test - Remove a certificate from an IIS binding.
        '''
        kwargs = {'name': 'FFFEEEDDDCCCBBBAAA0001112233445566778899',
                  'site': 'MyOtherTestSite', 'hostheader': 'myothertestsite.local',
                  'ipaddress': '*', 'port': 443}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.remove_cert_binding(**kwargs))

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value=CONTAINER_SETTING))
    def test_get_container_setting(self):
        '''
        Test - Get the value of the setting for the IIS container.
        '''
        kwargs = {'name': 'MyTestSite', 'container': 'AppPools',
                  'settings': ['managedPipelineMode']}
        with patch.dict(win_iis.__salt__):
            self.assertEqual(win_iis.get_container_setting(**kwargs),
                             {'managedPipelineMode': 'Integrated'})

    @patch('salt.modules.win_iis._srvmgr',
           MagicMock(return_value={'retcode': 0}))
    @patch('salt.modules.win_iis.get_container_setting',
           MagicMock(return_value={'managedPipelineMode': 'Integrated'}))
    def test_set_container_setting(self):
        '''
        Test - Set the value of the setting for an IIS container.
        '''
        kwargs = {'name': 'MyTestSite', 'container': 'AppPools',
                  'settings': {'managedPipelineMode': 'Integrated'}}
        with patch.dict(win_iis.__salt__):
            self.assertTrue(win_iis.set_container_setting(**kwargs))
