# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.win_disk as win_disk

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class MockKernel32(object):
    """
    Mock windll class
    """

    def __init__(self):
        pass

    @staticmethod
    def GetLogicalDrives():
        """
        Mock GetLogicalDrives method to return A and B.
        """
        return int("11", 2)


class MockWindll(object):
    """
    Mock windll class
    """

    def __init__(self):
        self.kernel32 = MockKernel32()


class MockCtypes(object):
    """
    Mock ctypes class
    """

    def __init__(self):
        self.windll = MockWindll()


class WinDiskTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.win_disk
    """

    def setup_loader_modules(self):
        return {win_disk: {"ctypes": MockCtypes()}}

    def test_letters(self):
        self.assertListEqual(win_disk.letters(), ["A", "B"])

    def test_usage(self):
        """
        Test if it return usage information for volumes mounted on this minion.
        """
        self.assertDictEqual(
            win_disk.usage(),
            {
                "A:\\": {
                    "available": None,
                    "1K-blocks": None,
                    "used": None,
                    "capacity": None,
                    "filesystem": "A:\\",
                },
                "B:\\": {
                    "available": None,
                    "1K-blocks": None,
                    "used": None,
                    "capacity": None,
                    "filesystem": "B:\\",
                },
            },
        )
