# -*- coding: utf-8 -*-
'''
This runner is used only for test purposes and servers no production purpose
'''
from __future__ import absolute_import
from __future__ import print_function
# Import python libs
import time
import salt.ext.six as six
from salt.ext.six.moves import range


def arg(*args, **kwargs):
    '''
    Output the given args and kwargs

    Kwargs will be filtered for 'private' keynames.
    '''
    kwargs = dict((k, v) for k, v in six.iteritems(kwargs)
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


def stdout_print():
    '''
    Print 'foo' and return 'bar'
    '''
    print ('foo')
    return 'bar'


def sleep(s_time=10):
    '''
    Sleep t seconds, then return True
    '''
    print (s_time)
    time.sleep(s_time)
    return True


def stream():
    '''
    Return True
    '''
    ret = True
    for i in range(1, 100):
        __jid_event__.fire_event({'message': 'Runner is {0}% done'.format(i)}, 'progress')
        time.sleep(0.1)
    return ret
