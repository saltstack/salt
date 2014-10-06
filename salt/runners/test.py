# -*- coding: utf-8 -*-
'''
This runner is used only for test purposes and servers no production purpose
'''
# Import python libs
from __future__ import print_function


def arg(*args, **kwargs):
    '''
    Output the given args and kwargs
    '''
    ret = {
        'args': args,
        'kwargs': kwargs,
    }
    print(ret)
    return ret
