# -*- coding: utf-8 -*-
'''
This runner is used only for test purposes and servers no production purpose
'''
# Import python libs
import time

# Import salt requirements
import salt.utils.event

def arg(*args, **kwargs):
    '''
    Output the given args and kwargs

    Kwargs will be filtered for 'private' keynames.
    '''
    kwargs = dict((k, v) for k, v in kwargs.iteritems()
            if not k.startswith('__'))

    ret = {
        'args': args,
        'kwargs': kwargs,
    }
    return ret


def raw_arg(*args, **kwargs):
    '''
    Output the given args and kwargs
    '''
    ret = {
        'args': args,
        'kwargs': kwargs,
    }
    return ret

def stream():
    '''
    Return True
    '''
    ret = True
    for i in range(1,100):
        progress('Runner is {0}% done'.format(i), outputter='pprint')
        time.sleep(0.1)
    return ret
