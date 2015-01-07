# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

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
from salt.exceptions import CommandExecutionError
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
        with patch.object(os.environ, 'pop', mock):
            self.assertEqual(environ.setval('key', False, True), None)

        mock = MagicMock(side_effect=Exception())
        with patch.object(os.environ, 'pop', mock):
            self.assertFalse(environ.setval('key', False, True))

        self.assertEqual(environ.setval('key', False), '')

        self.assertFalse(environ.setval('key', True))

    def test_setenv(self):
        '''
        Set multiple salt process environment variables from a dict.
        Returns a dict.
        '''
        self.assertFalse(environ.setenv('environ'))

        self.assertFalse(environ.setenv({'A': True},
                                        False,
                                        True,
                                        False))

        mock = MagicMock(return_value={})
        with patch.dict(os.environ, mock):
            mock = MagicMock(return_value=None)
            with patch.object(environ, 'setval', mock):
                self.assertEqual(environ.setenv({},
                                                False,
                                                True,
                                                False)['QT_QPA_PLATFORMTHEME'],
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
        self.assertFalse(environ.has_value(True))

        self.assertTrue(environ.has_value('QT_QPA_PLATFORMTHEME',
                                          'appmenu-qt5'))

        self.assertFalse(environ.has_value('QT_QPA_PLATFORMTHEME', 'value'))

        self.assertFalse(environ.has_value('key', 'value'))

        self.assertFalse(environ.has_value('key'))

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
        self.assertTrue(environ.items())


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EnvironTestCase, needs_daemon=False)
