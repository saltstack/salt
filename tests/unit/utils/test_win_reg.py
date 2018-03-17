# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_reg as win_reg


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinFunctionsTestCase(TestCase):
    '''
    Test cases for salt.utils.win_reg
    '''

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
                key='SOFTWARE\\Salt\\fake_key'
            ),
            False
        )

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
        expected = (False, 'Cannot find key: HKLM\\SOFTWARE\\Salt\\fake_key')
        self.assertEqual(
            win_reg.list_keys(
                hive='HKLM',
                key='SOFTWARE\\Salt\\fake_key'),
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
        expected = (False, 'Cannot find key: HKLM\\SOFTWARE\\Salt\\fake_key')
        self.assertEqual(
            win_reg.list_values(
                hive='HKLM',
                key='SOFTWARE\\Salt\\fake_key'
            ),
            expected
        )

    def test_read_value_existing(self):
        '''
        Test the list_values function using a well known registry key
        '''
        ret = win_reg.read_value(
            hive='HKLM',
            key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion',
            vname='ProgramFilesPath'
        )
        self.assertEqual(ret['vdata'], '%ProgramFiles%')

    def test_read_value_default(self):
        '''
        Test the read_value function reading the default value
        '''
        ret = win_reg.read_value(
            hive='HKLM',
            key='SOFTWARE\\Microsoft\\Windows\\CurrentVersion'
        )
        self.assertEqual(ret['vdata'], '(value not set)')

    def test_read_value_non_existing(self):
        '''
        Test the list_values function using a non existing registry key
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
        Test the list_values function using a non existing registry key
        '''
        expected = {
            'comment': 'Cannot find key: HKLM\\SOFTWARE\\Salt\\fake_key',
            'vdata': None,
            'vname': 'fake_name',
            'success': False,
            'hive': 'HKLM',
            'key': 'SOFTWARE\\Salt\\fake_key'
        }
        self.assertEqual(
            win_reg.read_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\fake_key',
                vname='fake_name'
            ),
            expected
        )

    @destructiveTest
    def test_set_value(self):
        '''
        Test the set_value function
        '''
        self.assertTrue(
            win_reg.set_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vname='fake_name',
                vdata='fake_data'
            )
        )
        expected = {
            'hive': 'HKLM',
            'key': 'SOFTWARE\\Salt\\Test\\',
            'success': True,
            'vdata': 'fake_data',
            'vname': 'fake_name',
            'vtype': 'REG_SZ'
        }
        self.assertEqual(
            win_reg.read_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vname='fake_name'
            ),
            expected
        )
        expected = {
            'Deleted': [
                'HKLM\\SOFTWARE\\Salt\\Test',
                'HKLM\\SOFTWARE\\Salt'
            ],
            'Failed': []
        }
        self.assertEqual(
            win_reg.delete_key_recursive(
                hive='HKLM',
                key='SOFTWARE\\Salt'
            ),
            expected
        )

    @destructiveTest
    def test_set_value_default(self):
        '''
        Test the set_value function
        '''
        self.assertTrue(
            win_reg.set_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vdata='fake_default_data'
            )
        )
        expected = {
            'hive': 'HKLM',
            'key': 'SOFTWARE\\Salt\\Test\\',
            'success': True,
            'vdata': 'fake_default_data',
            'vname': '(Default)',
            'vtype': 'REG_SZ'
        }
        self.assertEqual(
            win_reg.read_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
            ),
            expected
        )
        expected = {
            'Deleted': [
                'HKLM\\SOFTWARE\\Salt\\Test',
                'HKLM\\SOFTWARE\\Salt'
            ],
            'Failed': []
        }
        self.assertEqual(
            win_reg.delete_key_recursive(
                hive='HKLM',
                key='SOFTWARE\\Salt'
            ),
            expected
        )

    @destructiveTest
    def test_delete_value(self):
        '''
        Test the delete_value function
        '''
        self.assertTrue(
            win_reg.set_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vname='fake_name',
                vdata='fake_data'
            )
        )
        self.assertTrue(
            win_reg.delete_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vname='fake_name'
            )
        )
        expected = {
            'Deleted': [
                'HKLM\\SOFTWARE\\Salt\\Test',
                'HKLM\\SOFTWARE\\Salt'
            ],
            'Failed': []
        }
        self.assertEqual(
            win_reg.delete_key_recursive(
                hive='HKLM',
                key='SOFTWARE\\Salt'
            ),
            expected
        )

    def test_delete_value_non_existing(self):
        '''
        Test the delete_value function
        '''
        self.assertEqual(
            win_reg.delete_value(
                hive='HKLM',
                key='SOFTWARE\\Salt\\Test\\',
                vname='fake_name'
            ),
            None
        )
