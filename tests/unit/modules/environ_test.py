# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import environ
import os


# Globals
environ.__grains__ = {}
environ.__salt__ = {}
environ.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EnvironTestCase(TestCase):
    '''
    Test cases for salt.modules.environ
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EnvironTestCase, needs_daemon=False)
