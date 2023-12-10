"""
Utility functions used for values.

.. versionadded:: 2018.3.0
"""


def xor(*variables):
    """
    XOR definition for multiple variables
    """
    sum_ = False
    for value in variables:
        sum_ = sum_ ^ bool(value)
    return sum_
