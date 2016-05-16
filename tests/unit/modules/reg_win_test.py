# -*- coding: utf-8 -*-
'''
    :synopsis: Unit Tests for Windows Registry Module 'module.reg'
    :platform: Windows
    :maturity: develop
    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    versionadded:: Carbon
'''
# Import Python future libs
from __future__ import absolute_import
from __future__ import unicode_literals
# Import Python Libs
import sys
import time
# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import destructiveTest
# Import Salt Libs
from salt.modules import reg as win_mod_reg
try:
    from salt.ext.six.moves import winreg as _winreg  # pylint: disable=import-error,no-name-in-module
    NO_WINDOWS_MODULES = False
except ImportError:
    NO_WINDOWS_MODULES = True

PY2 = sys.version_info[0] == 2
# The following used to make sure we are not
# testing already existing data
# Note strftime retunrns a str, so we need to make it unicode
TIMEINT = int(time.time())

if PY2:
    TIME_INT_UNICODE = unicode(TIMEINT)
    TIMESTR = time.strftime('%X %x %Z').decode('utf-8')
else:
    TIMESTR = time.strftime('%X %x %Z')
    TIME_INT_UNICODE = str(TIMEINT)  # pylint: disable=R0204


# we do not need to prefix this with u, as we are
# using from __future__ import unicode_literals
UNICODETEST_WITH_SIGNS = 'Testing Unicode \N{COPYRIGHT SIGN},\N{TRADE MARK SIGN},\N{REGISTERED SIGN} '+TIMESTR
UNICODETEST_WITHOUT_SIGNS = 'Testing Unicode'+TIMESTR
UNICODE_TEST_KEY = 'UnicodeKey \N{TRADE MARK SIGN} '+TIME_INT_UNICODE
UNICODE_TEST_KEY_DEL = 'Delete Me \N{TRADE MARK SIGN} '+TIME_INT_UNICODE


@skipIf(NO_WINDOWS_MODULES, 'requires Windows OS to test Windows registry')
class RegWinTestCase(TestCase):
    '''
    Test cases for salt.modules.reg
    '''

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_read_reg_plain(self):
        '''
        Test - Read a registry value from a subkey using Pythen 2 Strings or
        Pythen 3 Bytes
        '''
        if not PY2:
            self.skipTest('Invalid for Python Version 2')

        subkey = b'Software\\Microsoft\\Windows NT\\CurrentVersion'
        vname = b'PathName'
        handle = _winreg.OpenKey(
                    _winreg.HKEY_LOCAL_MACHINE,
                    subkey,
                    0,
                    _winreg.KEY_ALL_ACCESS
                    )
        (current_vdata, dummy_current_vtype) = _winreg.QueryValueEx(handle, vname)
        _winreg.CloseKey(handle)

        test_vdata = win_mod_reg.read_value(b'HKEY_LOCAL_MACHINE', subkey, vname)[b'vdata']
        self.assertEqual(
            test_vdata, current_vdata)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_read_reg_unicode(self):
        '''
        Test - Read a registry value from a subkey using Pythen 2 Unicode
        or Pythen 3 Str i.e. Unicode
        '''
        subkey = 'Software\\Microsoft\\Windows NT\\CurrentVersion'
        vname = 'PathName'
        handle = _winreg.OpenKey(
                    _winreg.HKEY_LOCAL_MACHINE,
                    subkey,
                    0,
                    _winreg.KEY_ALL_ACCESS
                    )
        (current_vdata, dummy_current_vtype) = _winreg.QueryValueEx(handle, vname)
        _winreg.CloseKey(handle)

        test_vdata = win_mod_reg.read_value(
                        'HKEY_LOCAL_MACHINE',
                        subkey,
                        vname)['vdata']
        self.assertEqual(test_vdata, current_vdata)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_list_keys_fail(self):
        '''
        Test - Read list the keys under a subkey which does not exist.
        '''
        subkey = 'ThisIsJunkItDoesNotExistIhope'
        test_list = win_mod_reg.list_keys('HKEY_LOCAL_MACHINE', subkey)
        # returns a tuple with first item false, and second item a reason
        test = isinstance(test_list, tuple) and (not test_list[0])
        self.assertTrue(test)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_list_keys(self):
        '''
        Test - Read list the keys under a subkey
        '''
        subkey = 'Software\\Microsoft\\Windows NT\\CurrentVersion'
        test_list = win_mod_reg.list_keys('HKEY_LOCAL_MACHINE', subkey)
        test = len(test_list) > 5  # Their should be a lot more than 5 items
        self.assertTrue(test)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_list_values_fail(self):
        '''
        Test - List the values under a subkey which does not exist.
        '''
        subkey = 'ThisIsJunkItDoesNotExistIhope'
        test_list = win_mod_reg.list_values('HKEY_LOCAL_MACHINE', subkey)
        # returns a tuple with first item false, and second item a reason
        test = isinstance(test_list, tuple) and (not test_list[0])
        self.assertTrue(test)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_list_values(self):
        '''
        Test - List the values under a subkey.
        '''
        subkey = r'Software\Microsoft\Windows NT\CurrentVersion'
        test_list = win_mod_reg.list_values('HKEY_LOCAL_MACHINE', subkey)
        test = len(test_list) > 5  # There should be a lot more than 5 items
        self.assertTrue(test)

    # Not considering this destructive as its writing to a private space
    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_set_value_unicode(self):
        '''
        Test - set a registry plain text subkey name to a unicode string value
        '''
        vname = 'TestUniccodeString'
        subkey = 'Software\\SaltStackTest'
        test1_success = False
        test2_success = False
        test1_success = win_mod_reg.set_value(
                            'HKEY_LOCAL_MACHINE',
                            subkey,
                            vname,
                            UNICODETEST_WITH_SIGNS
                            )
        # Now use _winreg direct to see if it worked as expected
        if test1_success:
            handle = _winreg.OpenKey(
                        _winreg.HKEY_LOCAL_MACHINE,
                        subkey,
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            (current_vdata, dummy_current_vtype) = _winreg.QueryValueEx(handle, vname)
            _winreg.CloseKey(handle)
        test2_success = (current_vdata == UNICODETEST_WITH_SIGNS)
        self.assertTrue(test1_success and test2_success)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_set_value_unicode_key(self):
        '''
        Test - set a registry Unicode subkey name with unicode characters within
        to a integer
        '''
        test_success = win_mod_reg.set_value(
                        'HKEY_LOCAL_MACHINE',
                        'Software\\SaltStackTest',
                        UNICODE_TEST_KEY,
                        TIMEINT,
                        'REG_DWORD'
                        )
        self.assertTrue(test_success)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_del_value(self):
        '''
        Test - Create Directly and Delete with salt a registry value
        '''
        subkey = 'Software\\SaltStackTest'
        vname = UNICODE_TEST_KEY_DEL
        vdata = 'I will be deleted'
        if PY2:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_LOCAL_MACHINE,
                        subkey.encode('mbcs'),
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(
                handle,
                vname.encode('mbcs'),
                0,
                _winreg.REG_SZ,
                vdata.encode('mbcs')
                )
        else:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_LOCAL_MACHINE,
                        subkey,
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(handle, vname, 0, _winreg.REG_SZ, vdata)
        _winreg.CloseKey(handle)
        # time.sleep(15) # delays for 15 seconds
        test_success = win_mod_reg.delete_value(
                        'HKEY_LOCAL_MACHINE',
                        subkey,
                        vname
                        )
        self.assertTrue(test_success)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    def test_del_key_recursive_user(self):
        '''
        Test - Create directly key/value pair and Delete recusivly with salt
        '''
        subkey = 'Software\\SaltStackTest'
        vname = UNICODE_TEST_KEY_DEL
        vdata = 'I will be deleted recursive'
        if PY2:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_CURRENT_USER,
                        subkey.encode('mbcs'),
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(
                handle,
                vname.encode('mbcs'),
                0,
                _winreg.REG_SZ,
                vdata.encode('mbcs')
                )
        else:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_CURRENT_USER,
                        subkey,
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(handle, vname, 0, _winreg.REG_SZ, vdata)
        _winreg.CloseKey(handle)
        # time.sleep(15) # delays for 15 seconds so you can run regedit & watch it happen
        test_success = win_mod_reg.delete_key_recursive('HKEY_CURRENT_USER', subkey)
        self.assertTrue(test_success)

    @skipIf(not sys.platform.startswith("win"), "requires Windows OS")
    @destructiveTest
    def test_del_key_recursive_machine(self):
        '''
        This is a DESTRUCTIVE TEST it creates a new registry entry.
        And then destroys the registry entry recusively , however it is completed in its own space
        within the registry. We mark this as destructiveTest as it has the potential
        to detroy a machine if salt reg code has a large error in it.
        '''
        subkey = 'Software\\SaltStackTest'
        vname = UNICODE_TEST_KEY_DEL
        vdata = 'I will be deleted recursive'
        if PY2:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_LOCAL_MACHINE,
                        subkey.encode('mbcs'),
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(
                        handle,
                        vname.encode('mbcs'),
                        0,
                        _winreg.REG_SZ,
                        vdata.encode('mbcs')
                        )
        else:
            handle = _winreg.CreateKeyEx(
                        _winreg.HKEY_LOCAL_MACHINE,
                        subkey,
                        0,
                        _winreg.KEY_ALL_ACCESS
                        )
            _winreg.SetValueEx(handle, vname, 0, _winreg.REG_SZ, vdata)
        _winreg.CloseKey(handle)
        # time.sleep(15) # delays for 15 seconds so you can run regedit and watch it happen
        test_success = win_mod_reg.delete_key_recursive('HKEY_LOCAL_MACHINE', subkey)
        self.assertTrue(test_success)

    # pylint: disable=W0511
    # TODO: Test other hives, other than HKEY_LOCAL_MACHINE and HKEY_CURRENT_USER

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=C0413
    run_tests(RegWinTestCase, needs_daemon=False)
