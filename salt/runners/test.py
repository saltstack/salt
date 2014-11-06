# -*- coding: utf-8 -*-
'''
This runner is used only for test purposes and servers no production purpose
'''
# Import python libs
import pprint

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
    pprint.pprint(ret)
    return ret


def raw_arg(*args, **kwargs):
    '''
    Output the given args and kwargs
    '''
    ret = {
        'args': args,
        'kwargs': kwargs,
    }
    pprint.pprint(ret)
    return ret

def true(jid=None):
    '''
    Return True
    '''
    ret = True
    salt.utils.event.RunnerEvent(__opts__).fire_progress(jid, ret)
    return ret
