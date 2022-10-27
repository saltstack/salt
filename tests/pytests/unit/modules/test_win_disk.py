"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.modules.win_disk as win_disk


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


@pytest.fixture
def configure_loader_modules():
    return {win_disk: {"ctypes": MockCtypes()}}


def test_usage():
    """
    Test if it return usage information for volumes mounted on this minion.
    """
    assert win_disk.usage() == {
        "A:\\": {
            "available": None,
            "1K-blocks": None,
            "used": None,
            "capacity": None,
            "filesystem": "A:\\",
        }
    }
