import sys


def test_salt_system_encoding():
    encoding = sys.getdefaultencoding()
    assert __salt_system_encoding__ == encoding
