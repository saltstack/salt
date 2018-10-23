# -*- coding: utf-8 -*-
'''
Direct call executor module
'''
from __future__ import absolute_import, print_function, unicode_literals


def execute(opts, data, func, args, kwargs):
    '''
    Directly calls the given function with arguments
    '''
    return func(*args, **kwargs)
