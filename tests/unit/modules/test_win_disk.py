"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.win_disk as win_disk
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class MockKernel32:
    """
    Mock windll class
    """

    def __init__(self):
        pass

    @staticmethod
    def GetLogicalDrives():
        """
        Mock GetLogicalDrives method
        """
        return 1


class MockWindll:
    """
    Mock windll class
    """

    def __init__(self):
        self.kernel32 = MockKernel32()


class MockCtypes:
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

    # 'usage' function tests: 1

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
                }
            },
        )
