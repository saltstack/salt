"""
Module for testing that a __virtual__ function returning False will not be
available via the Salt Loader.
"""


def __virtual__():
    return (False, "The test_virtual execution module failed to load.")


def ping():
    return True
