# -*- coding: utf-8 -*-
'''
Direct call executor module
'''
from __future__ import absolute_import


def execute(opts, data, func, args, kwargs):
    '''
    Directly calls the given function with arguments
    '''
    return func(*args, **kwargs)
