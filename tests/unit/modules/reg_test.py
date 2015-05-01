# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import reg


class MockWinReg(object):
    '''
        Mock class of winreg
    '''
    HKEY_USERS = "HKEY_USERS"
    HKEY_CURRENT_USER = "HKEY_CURRENT_USER"
    HKEY_LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"
    KEY_ALL_ACCESS = True
    KEY_WOW64_64KEY = False
    flag = None
    flag1 = None
    flag2 = None

    def __init__(self):
        pass

    def OpenKeyEx(self, hkey2, path, bol, access_mask):
        '''
            Mock openKeyEx method
        '''
        if self.flag:
            return hkey2, path, bol, access_mask
        else:
            raise Exception("Error")

    @staticmethod
    def QueryValueEx(handle, key):
        '''
            Mock QueryValueEx method
        '''
        return [handle, key]

    def OpenKey(self, hkey2, path, bol, access_mask):
        '''
            Mock OpenKey Mothod
        '''
        if self.flag:
            return hkey2, path, bol, access_mask
        else:
            raise Exception("Error")

    @staticmethod
    def SetValueEx(handle, key, bol, _type, value):
        '''
            Mock SetValueEx method
        '''
        return handle, key, bol, _type, value

    @staticmethod
    def CloseKey(handle):
        '''
            Mock CloseKey method
        '''
        return handle

    @staticmethod
    def CreateKeyEx(hkey2, path, bol, access_mask):
        '''
            Mock CreateKeyEx method
        '''
        return hkey2, path, bol, access_mask

    def DeleteKeyEx(self, handle, key):
        '''
            Mock DeleteKeyEx method
        '''
        if self.flag1:
            return handle, key
        else:
            raise Exception("Error")

    def DeleteValue(self, handle, key):
        '''
            Mock DeleteValue
        '''
        if self.flag2:
            return handle, key
        else:
            raise Exception("Error")

reg._winreg = MockWinReg()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RegTestCase(TestCase):
    '''
        Test cases for salt.modules.reg
    '''
    def test_read_key(self):
        '''
            Test to read registry key value
        '''
        MockWinReg.flag = False
        self.assertEqual(reg.read_key("HKEY_LOCAL_MACHINE",
                                      "SOFTWARE\\Salt",
                                      "2014.7.0"),
                         None)

        MockWinReg.flag = True
        self.assertTrue(reg.read_key("HKEY_LOCAL_MACHINE",
                                     "SOFTWARE\\Salt",
                                     "2014.7.0"))

    def test_set_key(self):
        '''
            Test to set a registry key
        '''
        self.assertFalse(reg.set_key("HKEY_CURRENT_USER",
                                     "SOFTWARE\\Salt",
                                     "2014.7.0",
                                     "0.97")
                         )

        MockWinReg.flag = True
        self.assertTrue(reg.set_key("HKEY_CURRENT_USER",
                                    "SOFTWARE\\Salt",
                                    "2014.7.0",
                                    "0.97",
                                    "OpenKey")
                        )

        MockWinReg.flag = False
        self.assertTrue(reg.set_key("HKEY_CURRENT_USER",
                                    "SOFTWARE\\Salt",
                                    "2014.7.0",
                                    "0.97",
                                    "OpenKey")
                        )

    def test_create_key(self):
        '''
            Test to Create a registry key
        '''
        MockWinReg.flag = True
        self.assertTrue(reg.create_key("HKEY_CURRENT_USER",
                                       "SOFTWARE\\Salt",
                                       "2014.7.0"
                                       )
                        )

        MockWinReg.flag = False
        self.assertTrue(reg.create_key("HKEY_CURRENT_USER",
                                       "SOFTWARE\\Salt",
                                       "2014.7.0"
                                       )
                        )

    def test_delete_key(self):
        '''
            Test to delete key
        '''
        MockWinReg.flag = True
        MockWinReg.flag1 = True
        self.assertTrue(reg.delete_key("HKEY_CURRENT_USER",
                                       "SOFTWARE\\Salt",
                                       "2014.7.0"
                                       )
                        )

        MockWinReg.flag = True
        MockWinReg.flag1 = False
        MockWinReg.flag2 = False
        self.assertFalse(reg.delete_key("HKEY_CURRENT_USER",
                                        "SOFTWARE\\Salt",
                                        "2014.7.0"
                                        )
                         )

        MockWinReg.flag = True
        MockWinReg.flag1 = False
        MockWinReg.flag2 = True
        self.assertTrue(reg.delete_key("HKEY_CURRENT_USER",
                                       "SOFTWARE\\Salt",
                                       "2014.7.0"
                                       )
                        )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(RegTestCase, needs_daemon=False)
