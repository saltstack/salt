# -*- coding: utf-8 -*-
'''
Display no output
=================

No output is produced when this outputter is selected
'''

# Define the module's virtual name
__virtualname__ = 'quiet'


def __virtual__():
    return __virtualname__


def output(ret, **kwargs):  # pylint: disable=unused-argument
    '''
    Don't display data. Used when you only are interested in the
    return.
    '''
    return ''
