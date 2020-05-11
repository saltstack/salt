# -*- coding: utf-8 -*-
'''
Utility functions used for values.

.. versionadded:: 2018.3.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals


def xor(*variables):
    '''
    XOR definition for multiple variables
    '''
    sum_ = False
    for value in variables:
        sum_ = sum_ ^ bool(value)
    return sum_
