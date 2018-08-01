# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest, generate_random_name
from tests.support.mock import NO_MOCK, NO_MOCK_REASON
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
import salt.utils.platform
import salt.utils.win_dacl as win_dacl
import salt.utils.win_reg as win_reg

import pywintypes
import win32security

FAKE_KEY = 'SOFTWARE\\{0}'.format(generate_random_name('SaltTesting-'))


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinDaclTestCase(TestCase):
    '''
    Test cases for salt.utils.win_dacl in the registry
    '''
    def test_get_sid_string(self):
        '''
        Validate getting a pysid object from a name
        '''
        sid_obj = win_dacl.get_sid('Administrators')
        self.assertTrue(
            isinstance(sid_obj, pywintypes.SIDType)
        )
        self.assertEqual(
            win32security.LookupAccountSid(None, sid_obj)[0],
            'Administrators'
        )

    def test_get_sid_sid_string(self):
        '''
        Validate getting a pysid object from a SID string
        '''
        sid_obj = win_dacl.get_sid('S-1-5-32-544')
        self.assertTrue(
            isinstance(sid_obj, pywintypes.SIDType)
        )
        self.assertEqual(
            win32security.LookupAccountSid(None, sid_obj)[0],
            'Administrators'
        )

    def test_get_sid_string(self):
        '''
        Validate getting a pysid object from a SID string
        '''
        sid_obj = win_dacl.get_sid('Administrators')
        self.assertTrue(
            isinstance(sid_obj, pywintypes.SIDType)
        )
        self.assertEqual(
            win_dacl.get_sid_string(sid_obj),
            'S-1-5-32-544'
        )

    def test_get_sid_string_none(self):
        '''
        Validate getting a pysid object from None (NULL SID)
        '''
        sid_obj = win_dacl.get_sid(None)
        self.assertTrue(
            isinstance(sid_obj, pywintypes.SIDType)
        )
        self.assertEqual(
            win_dacl.get_sid_string(sid_obj),
            'S-1-0-0'
        )

    def test_get_name(self):
        '''
        Get the name
        '''
        # Case
        self.assertEqual(
            win_dacl.get_name('adMiniStrAtorS'),
            'Administrators'
        )
        # SID String
        self.assertEqual(
            win_dacl.get_name('S-1-5-32-544'),
            'Administrators'
        )
        # SID Object
        sid_obj = win_dacl.get_sid('Administrators')
        self.assertTrue(
            isinstance(sid_obj, pywintypes.SIDType)
        )
        self.assertEqual(
            win_dacl.get_name(sid_obj),
            'Administrators'
        )

@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), 'System is not Windows')
class WinDaclRegTestCase(TestCase):
    '''
    Test cases for salt.utils.win_dacl in the registry
    '''
    @destructiveTest
    def test_owner(self):
        '''
        Test the set_owner function
        Test the get_owner function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))

            self.assertTrue(
                win_dacl.set_owner(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                ))
            self.assertEqual(
                win_dacl.get_owner(
                    obj_name='HKLM\\' + FAKE_KEY,
                    obj_type='registry'
                ),
                'Backup Operators'
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_primary_group(self):
        '''
        Test the set_primary_group function
        Test the get_primary_group function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))

            self.assertTrue(
                win_dacl.set_primary_group(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                ))
            self.assertEqual(
                win_dacl.get_primary_group(
                    obj_name='HKLM\\' + FAKE_KEY,
                    obj_type='registry'
                ),
                'Backup Operators'
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_set_permissions(self):
        '''
        Test the set_permissions function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))
            self.assertTrue(
                win_dacl.set_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permissions='full_control',
                    access_mode='grant',
                    obj_type='registry',
                    reset_perms=False,
                    protected=None
                ))
            expected = {
                'Not Inherited': {
                    'Backup Operators': {
                        'grant': {
                            'applies to': 'This key and subkeys',
                            'permissions': ['Full Control']
                        }
                    }
                }
            }
            self.assertEqual(
                win_dacl.get_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_get_permissions(self):
        '''
        Test the get_permissions function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))
            self.assertTrue(
                win_dacl.set_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permissions='full_control',
                    access_mode='grant',
                    obj_type='registry',
                    reset_perms=False,
                    protected=None
                ))
            expected = {
                'Not Inherited': {
                    'Backup Operators': {
                        'grant': {
                            'applies to': 'This key and subkeys',
                            'permissions': ['Full Control']
                        }
                    }
                }
            }
            self.assertEqual(
                win_dacl.get_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                ),
                expected
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_has_permission(self):
        '''
        Test the has_permission function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))
            self.assertTrue(
                win_dacl.set_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permissions='full_control',
                    access_mode='grant',
                    obj_type='registry',
                    reset_perms=False,
                    protected=None
                ))
            # Test has_permission exact
            self.assertTrue(
                win_dacl.has_permission(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permission='full_control',
                    access_mode='grant',
                    obj_type='registry',
                    exact=True
                )
            )
            # Test has_permission contains
            self.assertTrue(
                win_dacl.has_permission(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permission='read',
                    access_mode='grant',
                    obj_type='registry',
                    exact=False
                )
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_rm_permissions(self):
        '''
        Test the rm_permissions function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))
            self.assertTrue(
                win_dacl.set_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    permissions='full_control',
                    access_mode='grant',
                    obj_type='registry',
                    reset_perms=False,
                    protected=None
                ))
            self.assertTrue(
                win_dacl.rm_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                )
            )
            self.assertEqual(
                win_dacl.get_permissions(
                    obj_name='HKLM\\' + FAKE_KEY,
                    principal='Backup Operators',
                    obj_type='registry'
                ),
                {}
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)

    @destructiveTest
    def test_inheritance(self):
        '''
        Test the set_inheritance function
        Test the get_inheritance function
        '''
        try:
            self.assertTrue(
                win_reg.set_value(
                    hive='HKLM',
                    key=FAKE_KEY,
                    vname='fake_name',
                    vdata='fake_data'
                ))

            self.assertTrue(
                win_dacl.set_inheritance(
                    obj_name='HKLM\\' + FAKE_KEY,
                    enabled=True,
                    obj_type='registry',
                    clear=False
                ))
            self.assertTrue(
                win_dacl.get_inheritance(
                    obj_name='HKLM\\' + FAKE_KEY,
                    obj_type='registry'
                )
            )
            self.assertTrue(
                win_dacl.set_inheritance(
                    obj_name='HKLM\\' + FAKE_KEY,
                    enabled=False,
                    obj_type='registry',
                    clear=False
                ))
            self.assertFalse(
                win_dacl.get_inheritance(
                    obj_name='HKLM\\' + FAKE_KEY,
                    obj_type='registry'
                )
            )
        finally:
            win_reg.delete_key_recursive(hive='HKLM', key=FAKE_KEY)
