# -*- coding: utf-8 -*-
'''
Unit tests for salt/modules/salt_version.py
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt libs
import salt.modules.salt_version as salt_version
import salt.version


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltVersionTestCase(TestCase):
    '''
    Test cases for salt.modules.salt_version
    '''

    # get_release_number tests: 3

    def test_get_release_number_no_version(self):
        '''
        Test that None is returned when the codename isn't found.
        '''
        assert salt_version.get_release_number('foo') is None

    @patch('salt.version.SaltStackVersion.LNAMES', {'foo': (12345, 0)})
    def test_get_release_number_unassigned(self):
        '''
        Test that a string is returned when a version is found, but unassigned.
        '''
        mock_str = 'No version assigned.'
        assert salt_version.get_release_number('foo') == mock_str

    def test_get_release_number_success(self):
        '''
        Test that a version is returned for a released codename
        '''
        assert salt_version.get_release_number('Oxygen') == '2018.3'

    # is_equal tests: 3

    @patch('salt.version.SaltStackVersion.LNAMES', {'foo': (1900, 5)})
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='1900.5.0'))
    def test_is_equal_success(self):
        '''
        Test that the current version is equal to the codename
        '''
        assert salt_version.is_equal('foo') is True

    @patch('salt.version.SaltStackVersion.LNAMES', {'Oxygen': (2018, 3),
                                                    'Nitrogen': (2017, 7)})
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_equal_older_version(self):
        '''
        Test that when an older codename is passed in, the function returns False.
        '''
        assert salt_version.is_equal('Nitrogen') is False

    @patch('salt.version.SaltStackVersion.LNAMES', {'Fluorine': (salt.version.MAX_SIZE - 100, 0)})
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_equal_newer_version(self):
        '''
        Test that when a newer codename is passed in, the function returns False
        '''
        assert salt_version.is_equal('Fluorine') is False

    # is_newer tests: 3

    @patch('salt.modules.salt_version.get_release_number', MagicMock(return_value='No version assigned.'))
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_newer_success(self):
        '''
        Test that the current version is newer than the codename
        '''
        assert salt_version.is_newer('Fluorine') is True

    @patch('salt.version.SaltStackVersion.LNAMES', {'Oxygen': (2018, 3)})
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_newer_with_equal_version(self):
        '''
        Test that when an equal codename is passed in, the function returns False.
        '''
        assert salt_version.is_newer('Oxygen') is False

    @patch('salt.version.SaltStackVersion.LNAMES', {'Oxygen': (2018, 3),
                                                    'Nitrogen': (2017, 7)})
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_newer_with_older_version(self):
        '''
        Test that when an older codename is passed in, the function returns False.
        '''
        assert salt_version.is_newer('Nitrogen') is False

    # is_older tests: 3

    @patch('salt.modules.salt_version.get_release_number', MagicMock(return_value='2017.7'))
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_older_success(self):
        '''
        Test that the current version is older than the codename
        '''
        assert salt_version.is_older('Nitrogen') is True

    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    @patch('salt.version.SaltStackVersion.LNAMES', {'Oxygen': (2018, 3)})
    def test_is_older_with_equal_version(self):
        '''
        Test that when an equal codename is passed in, the function returns False.
        '''
        assert salt_version.is_older('Oxygen') is False

    @patch('salt.modules.salt_version.get_release_number', MagicMock(return_value='No version assigned.'))
    @patch('salt.version.SaltStackVersion', MagicMock(return_value='2018.3.2'))
    def test_is_older_with_newer_version(self):
        '''
        Test that when an newer codename is passed in, the function returns False.
        '''
        assert salt_version.is_older('Fluorine') is False

    # _check_release_cmp tests: 2

    def test_check_release_cmp_no_codename(self):
        '''
        Test that None is returned when the codename isn't found.
        '''
        assert salt_version._check_release_cmp('foo') is None

    def test_check_release_cmp_success(self):
        '''
        Test that an int is returned from the version compare
        '''
        assert isinstance(salt_version._check_release_cmp('Oxygen'), int)
