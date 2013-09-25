# -*- coding: utf-8 -*-
'''
The raw outputter outputs the data via the python print function and is shown
in a raw state. This was the original outputter used by Salt before the
outputter system was developed.
'''


def output(data):
    '''
    Rather basic....
    '''
    return str(data)
