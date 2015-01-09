# -*- coding: utf-8 -*-
'''
This runner is used only for test purposes and servers no production purpose
'''
from __future__ import absolute_import
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


def stream():
    '''
    Return True
    '''
    ret = True
    for i in range(1, 100):
        __progress__('Runner is {0}% done'.format(i), outputter='pprint')
        time.sleep(0.1)
    return ret
