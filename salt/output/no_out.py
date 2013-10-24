# -*- coding: utf-8 -*-
'''
Display no output.
'''

# Define the module's virtual name
__virtualname__ = 'quiet'


def __virtual__():
    return __virtualname__


def output(ret):
    '''
    Don't display data. Used when you only are interested in the
    return.
    '''
    return ''
