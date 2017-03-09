# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import win_license as license

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

license.__salt__ = {}


class LicenseTestCase(TestCase):

    def test_installed(self):
        '''
            Test to see if the given license key is installed
        '''
        mock = MagicMock(return_value='Partial Product Key: ABCDE')
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            out = license.installed('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /dli')
            self.assertTrue(out)

    def test_installed_diff(self):
        '''
            Test to see if the given license key is installed when the key is different
        '''
        mock = MagicMock(return_value='Partial Product Key: 12345')
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            out = license.installed('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /dli')
            self.assertFalse(out)

    def test_install(self):
        '''
            Test installing the given product key
        '''
        mock = MagicMock()
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            license.install('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /ipk '
                                         'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')

    def test_uninstall(self):
        '''
            Test uninstalling the given product key
        '''
        mock = MagicMock()
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            license.uninstall()
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /upk')

    def test_activate(self):
        '''
            Test activating the current product key
        '''
        mock = MagicMock()
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            license.activate()
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /ato')

    def test_licensed(self):
        '''
            Test checking if the minion is licensed
        '''
        mock = MagicMock(return_value='License Status: Licensed')
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            license.licensed()
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /dli')

    def test_info(self):
        '''
            Test getting the info about the current license key
        '''
        expected = {
            'description': 'Prof',
            'licensed': True,
            'name': 'Win7',
            'partial_key': '12345'
        }

        mock = MagicMock(return_value='Name: Win7\r\nDescription: Prof\r\nPartial Product Key: 12345\r\n'
                                      'License Status: Licensed')
        with patch.dict(license.__salt__, {'cmd.run': mock}):
            out = license.info()
            mock.assert_called_once_with(r'cscript C:\Windows\System32\slmgr.vbs /dli')
            self.assertEqual(out, expected)
