# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import win_disk


class MockKernel32(object):
    '''
    Mock windll class
    '''
    def __init__(self):
        pass

    @staticmethod
    def GetLogicalDrives():
        '''
        Mock GetLogicalDrives method
        '''
        return 1


class MockWindll(object):
    '''
    Mock windll class
    '''
    def __init__(self):
        self.kernel32 = MockKernel32()


class MockCtypes(object):
    '''
    Mock ctypes class
    '''
    def __init__(self):
        self.windll = MockWindll()

win_disk.ctypes = MockCtypes()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinDiskTestCase(TestCase):
    '''
    Test cases for salt.modules.win_disk
    '''
    # 'usage' function tests: 1

    def test_usage(self):
        '''
        Test if it return usage information for volumes mounted on this minion.
        '''
        self.assertDictEqual(win_disk.usage(),
                             {'A:\\': {'available': None,
                                       '1K-blocks': None,
                                       'used': None,
                                       'capacity': None,
                                       'filesystem': 'A:\\'}})
