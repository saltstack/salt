"""
Wheel functions for integration tests
"""


def failure():
    __context__["retcode"] = 1
    return False


def success():
    return True
