# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

import pytest

# Import Salt Testing Libs
from tests.support.mock import patch
from tests.support.helpers import generate_random_name
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_reg as win_reg

UNICODE_KEY = 'Unicode Key \N{TRADE MARK SIGN}'
UNICODE_VALUE = 'Unicode Value ' \
                '\N{COPYRIGHT SIGN},\N{TRADE MARK SIGN},\N{REGISTERED SIGN}'
FAKE_KEY = 'SOFTWARE\\{0}'.format(generate_random_name('SaltTesting-'))


@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinFunctionsTestCase(TestCase):
    '''
    Test cases for salt.utils.win_reg
    '''
    def test_broadcast_change_success(self):
        '''
        Tests the broadcast_change function
        '''
        with patch('win32gui.SendMessageTimeout', return_value=('', 0)):
            self.assertEqual(win_reg.broadcast_change(), True)

    def test_broadcast_change_fail(self):
        '''
        Tests the broadcast_change function failure
        '''
        with patch('win32gui.SendMessageTimeout', return_value=('', 1)):
            self.assertEqual(win_reg.broadcast_change(), False)

    def test_key_exists_existing(self):
        '''
        Tests the key exists function using a well known registry key
        '''
        self.assertEqual(
            win_reg.key_exists(
                hive='HKLM',
                key='SOFTWARE\\Microsoft'
            ),
            True
        )

    def test_key_exists_non_existing(self):
        '''
        Tests the key exists function using a non existing registry key
        '''
        self.assertEqual(
            win_reg.key_exists(
                hive='HKLM',
                key=FAKE_KEY
            ),
            False
        )

    def test_list_keys_existing(self):
        '''
        Test the list_keys function using a well known registry key
        '''
        self.assertIn(
            'Microsoft',
            win_reg.list_keys(
                hive='HKLM',
                key='SOFTWARE'
            )
        )

    def test_list_keys_non_existing(self):
        '''
        Test the list_keys function using a non existing registry key
        '''
        expected = (False, 'Cannot find key: HKLM\\{0}'.format(FAKE_KEY))
        self.assertEqual(
            win_reg.list_keys(
                hive='HKLM',
                key=FAKE_KEY
            ),
            expected
        )

    def test_list_values_existing(self):
        '''
        Test the list_values function using a well known registry key
        '''
        values = win_reg.list_values(
            hive='HKLM',
            key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
        )
        keys = []
        for value in values:
            keys.append(value['vname'])
        self.assertIn('ProgramFilesDir', keys)

    def test_list_values_non_existing(self):
        '''
        Test the list_values function using a non existing registry key
        '''
        expected = (False, 'Cannot find key: HKLM\\{0}'.format(FAKE_KEY))
        self.assertEqual(
            win_reg.list_values(
                hive='HKLM',
                key=FAKE_KEY
            ),
            expected
        )

    def test_read_value_existing(self):
        '''
        Test the read_value function using a well known registry value
        '''
        ret = win_reg.read_value(
            hive='HKLM',
            key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion',
            vname='ProgramFilesPath'
        )
        self.assertEqual(ret['vdata'], '%ProgramFiles%')

    def test_read_value_default(self):
        '''
        Test the read_value function reading the default value using a well
        known registry key
        '''
        ret = win_reg.read_value(
            hive='HKLM',
            key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
        )
        self.assertEqual(ret['vdata'], '(value not set)')

    def test_read_value_non_existing(self):
        '''
        Test the read_value function using a non existing value pair
        '''
        expected = {
            'comment': 'Cannot find fake_name in HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion',
            'vdata': None,
            'vname': 'fake_name',
            'success': False,
            'hive': 'HKLM',
            'key': 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
        }
        self.assertEqual(
            win_reg.read_value(
                hive='HKLM',
                key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion',
                vname='fake_name'
            ),
            expected
        )

    def test_read_value_non_existing_key(self):
        '''
        Test the read_value function using a non existing registry key
        '''
        expected = {
            'comment': 'Cannot find key: HKLM\\{0}'.format(FAKE_KEY),
            'vdata': None,
            'vname': 'fake_name',
            'success': False,
            'hive': 'HKLM',
            'key': FAKE_KEY
        }
        self.assertEqual(
            win_reg.read_value(
                hive='HKLM',
                key=FAKE_KEY,
                vname='fake_name'
            ),
            expected
        )

    @pytest.mark.destructive_test
    def test_set_value(self):
        '''
        Test the set_value function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': FAKE_KEY,
                'success': True,
                'vdata': 'fake_data',
                'vname': 'fake_name',
                'vtype': 'REG_SZ'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_set_value_default(self):
        '''
        Test the set_value function on the default value
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vdata='fake_default_data'
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': FAKE_KEY,
                'success': True,
                'vdata': 'fake_default_data',
                'vname': '(Default)',
                'vtype': 'REG_SZ'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_set_value_unicode_key(self):
        '''
        Test the set_value function on a unicode key
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key='{0}\\{1}'.format(FAKE_KEY, UNICODE_KEY),
                    vname='fake_name',
                    vdata='fake_value'
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': '{0}\\{1}'.format(FAKE_KEY, UNICODE_KEY),
                'success': True,
                'vdata': 'fake_value',
                'vname': 'fake_name',
                'vtype': 'REG_SZ'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key='{0}\\{1}'.format(FAKE_KEY, UNICODE_KEY),
                    vname='fake_name'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_set_value_unicode_value(self):
        '''
        Test the set_value function on a unicode value
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_unicode',
                    vdata=UNICODE_VALUE
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': FAKE_KEY,
                'success': True,
                'vdata': UNICODE_VALUE,
                'vname': 'fake_unicode',
                'vtype': 'REG_SZ'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_unicode'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_set_value_reg_dword(self):
        '''
        Test the set_value function on a unicode value
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='dword_value',
                    vdata=123,
                    vtype='REG_DWORD'
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': FAKE_KEY,
                'success': True,
                'vdata': 123,
                'vname': 'dword_value',
                'vtype': 'REG_DWORD'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='dword_value'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_set_value_reg_qword(self):
        '''
        Test the set_value function on a unicode value
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='qword_value',
                    vdata=123,
                    vtype='REG_QWORD'
                )
            )
            expected = {
                'hive': 'HKLM',
                'key': FAKE_KEY,
                'success': True,
                'vdata': 123,
                'vname': 'qword_value',
                'vtype': 'REG_QWORD'
            }
            self.assertEqual(
                win_reg.read_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='qword_value'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_delete_value(self):
        '''
        Test the delete_value function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                )
            )
            self.assertTrue(
                win_reg.delete_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name'
                )
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    def test_delete_value_non_existing(self):
        '''
        Test the delete_value function on non existing value
        '''
        self.assertEqual(
            win_reg.delete_value(
                hive='HKLM',
                key=FAKE_KEY,
                vname='fake_name'
            ),
            None
        )

    @pytest.mark.destructive_test
    def test_delete_value_unicode(self):
        '''
        Test the delete_value function on a unicode value
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_unicode',
                    vdata=UNICODE_VALUE
                )
            )
            self.assertTrue(
                win_reg.delete_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_unicode'
                )
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @pytest.mark.destructive_test
    def test_delete_key_unicode(self):
        '''
        Test the delete_value function on value within a unicode key
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key='{0}\\{1}'.format(FAKE_KEY, UNICODE_KEY),
                    vname='fake_name',
                    vdata='fake_value'
                )
            )
            expected = {
                'Deleted': ['HKLM\\{0}\\{1}\\'.format(FAKE_KEY, UNICODE_KEY)],
                'Failed': []
            }
            self.assertEqual(
                win_reg.delete_key_recursive(
                    hive='HKLM',
                    key='{0}\\{1}\\'.format(FAKE_KEY, UNICODE_KEY),
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)
