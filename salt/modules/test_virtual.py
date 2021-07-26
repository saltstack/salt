"""
Module for running arbitrary tests with a __virtual__ function
"""


def __virtual__():
    return (False, "The test_virtual execution module failed to load.")


def ping():
    return True
