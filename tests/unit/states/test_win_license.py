# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.states import win_license as license

# Import Salt Testing Libs
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

license.__salt__ = {}


class LicenseTestCase(TestCase):

    def test_activate(self):
        '''
            Test activating the given product key
        '''
        expected = {
            'changes': {},
            'comment': 'Windows is now activated.',
            'name': 'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE',
            'result': True
        }

        info = {
            'description': 'Prof',
            'licensed': False,
            'name': 'Win7',
            'partial_key': 'XXXXX'
        }

        info_mock = MagicMock(return_value=info)
        install_mock = MagicMock(return_value='Installed successfully')
        activate_mock = MagicMock(return_value='Activated successfully')
        with patch.dict(license.__salt__, {'license.info': info_mock,
                                           'license.install': install_mock,
                                           'license.activate': activate_mock}):
            out = license.activate('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            info_mock.assert_called_once_with()
            install_mock.assert_called_once_with('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            activate_mock.assert_called_once_with()
            self.assertEqual(out, expected)

    def test_installed_not_activated(self):
        '''
            Test activating the given product key when the key is installed but not activated
        '''
        expected = {
            'changes': {},
            'comment': 'Windows is now activated.',
            'name': 'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE',
            'result': True
        }

        info = {
            'description': 'Prof',
            'licensed': False,
            'name': 'Win7',
            'partial_key': 'ABCDE'
        }

        info_mock = MagicMock(return_value=info)
        install_mock = MagicMock(return_value='Installed successfully')
        activate_mock = MagicMock(return_value='Activated successfully')
        with patch.dict(license.__salt__, {'license.info': info_mock,
                                           'license.install': install_mock,
                                           'license.activate': activate_mock}):
            out = license.activate('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            info_mock.assert_called_once_with()
            assert not install_mock.called
            activate_mock.assert_called_once_with()
            self.assertEqual(out, expected)

    def test_installed_activated(self):
        '''
            Test activating the given product key when its already activated
        '''
        expected = {
            'changes': {},
            'comment': 'Windows is already activated.',
            'name': 'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE',
            'result': True
        }

        info = {
            'description': 'Prof',
            'licensed': True,
            'name': 'Win7',
            'partial_key': 'ABCDE'
        }

        info_mock = MagicMock(return_value=info)
        install_mock = MagicMock(return_value='Installed successfully')
        activate_mock = MagicMock(return_value='Activated successfully')
        with patch.dict(license.__salt__, {'license.info': info_mock,
                                           'license.install': install_mock,
                                           'license.activate': activate_mock}):
            out = license.activate('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            info_mock.assert_called_once_with()
            assert not install_mock.called
            assert not activate_mock.called
            self.assertEqual(out, expected)

    def test_installed_install_fail(self):
        '''
            Test activating the given product key when the install fails
        '''
        expected = {
            'changes': {},
            'comment': 'Unable to install the given product key is it valid?',
            'name': 'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE',
            'result': False
        }

        info = {
            'description': 'Prof',
            'licensed': False,
            'name': 'Win7',
            'partial_key': '12345'
        }

        info_mock = MagicMock(return_value=info)
        install_mock = MagicMock(return_value='Failed')
        activate_mock = MagicMock()
        with patch.dict(license.__salt__, {'license.info': info_mock,
                                           'license.install': install_mock,
                                           'license.activate': activate_mock}):
            out = license.activate('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            info_mock.assert_called_once_with()
            install_mock.assert_called_once_with('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            assert not activate_mock.called
            self.assertEqual(out, expected)

    def test_installed_activate_fail(self):
        '''
            Test activating the given product key when the install fails
        '''
        expected = {
            'changes': {},
            'comment': 'Unable to activate the given product key.',
            'name': 'AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE',
            'result': False
        }

        info = {
            'description': 'Prof',
            'licensed': False,
            'name': 'Win7',
            'partial_key': 'ABCDE'
        }

        info_mock = MagicMock(return_value=info)
        install_mock = MagicMock()
        activate_mock = MagicMock(return_value='Failed to activate')
        with patch.dict(license.__salt__, {'license.info': info_mock,
                                           'license.install': install_mock,
                                           'license.activate': activate_mock}):
            out = license.activate('AAAAA-AAAAA-AAAAA-AAAA-AAAAA-ABCDE')
            info_mock.assert_called_once_with()
            assert not install_mock.called
            activate_mock.assert_called_once_with()
            self.assertEqual(out, expected)
