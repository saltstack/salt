# -*- coding: utf-8 -*-
'''
The python pretty print system was the default outputter. This outputter
simply passed the data passed into it through the pprint module.
'''

# Import python libs
import pprint


def __virtual__():
    '''
    Change the name to pprint
    '''
    return 'pprint'


def output(data):
    '''
    Print out via pretty print
    '''
    if isinstance(data, Exception):
        data = str(data)
    if 'output_indent' in __opts__ and __opts__['output_indent'] >= 0:
        return pprint.pformat(data, indent=__opts__['output_indent'])
    return pprint.pformat(data)
