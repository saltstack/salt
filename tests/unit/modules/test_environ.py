# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import environ


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EnvironTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.environ
    '''
    loader_module = environ

    def test_setval(self):
        '''
        Test for set a single salt process environment variable. Returns True
        on success.
        '''
        mock = MagicMock(return_value=None)
        with patch.dict(os.environ, {}):
            self.assertEqual(environ.setval('key', False, True), None)

        mock = MagicMock(side_effect=Exception())
        with patch.dict(os.environ, {}):
            self.assertFalse(environ.setval('key', False, True))

        mock_environ = {}
        with patch.dict(os.environ, mock_environ):
            self.assertEqual(environ.setval('key', False), '')

        with patch.dict(os.environ, mock_environ):
            self.assertFalse(environ.setval('key', True))

    @patch('salt.utils.is_windows', MagicMock(return_value=True))
    def test_set_val_permanent(self):
        with patch.dict(os.environ, {}):
            with patch.dict(environ.__salt__, {'reg.set_value': MagicMock(),
                                               'reg.delete_value': MagicMock()}):

                environ.setval('key', 'Test', permanent=True)
                environ.__salt__['reg.set_value'].assert_called_with('HKCU', 'Environment', 'key', 'Test')

                environ.setval('key', False, false_unsets=True, permanent=True)
                environ.__salt__['reg.set_value'].asset_not_called()
                environ.__salt__['reg.delete_value'].assert_called_with('HKCU', 'Environment', 'key')

                key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
                environ.setval('key', 'Test', permanent='HKLM')
                environ.__salt__['reg.set_value'].assert_called_with('HKLM', key, 'key', 'Test')

    def test_setenv(self):
        '''
        Set multiple salt process environment variables from a dict.
        Returns a dict.
        '''
        mock_environ = {'key': 'value'}
        with patch.dict(os.environ, mock_environ):
            self.assertFalse(environ.setenv('environ'))

        with patch.dict(os.environ, mock_environ):
            self.assertFalse(environ.setenv({'A': True},
                                            False,
                                            True,
                                            False))

        with patch.dict(os.environ, mock_environ):
            mock_setval = MagicMock(return_value=None)
            with patch.object(environ, 'setval', mock_setval):
                self.assertEqual(environ.setenv({}, False, True, False)['key'],
                                 None)

    def test_get(self):
        '''
        Get a single salt process environment variable.
        '''
        self.assertFalse(environ.get(True))

        self.assertEqual(environ.get('key'), '')

    def test_has_value(self):
        '''
        Determine whether the key exists in the current salt process
        environment dictionary. Optionally compare the current value
        of the environment against the supplied value string.
        '''
        mock_environ = {}
        with patch.dict(os.environ, mock_environ):
            self.assertFalse(environ.has_value(True))

            os.environ['salty'] = 'yes'
            self.assertTrue(environ.has_value('salty', 'yes'))

            os.environ['too_salty'] = 'no'
            self.assertFalse(environ.has_value('too_salty', 'yes'))

            self.assertFalse(environ.has_value('key', 'value'))

            os.environ['key'] = 'value'
            self.assertTrue(environ.has_value('key'))

    def test_item(self):
        '''
        Get one or more salt process environment variables.
        Returns a dict.
        '''
        self.assertEqual(environ.item(None), {})

    def test_items(self):
        '''
        Return a dict of the entire environment set for the salt process
        '''
        self.assertNotEqual(list(environ.items()), [])
