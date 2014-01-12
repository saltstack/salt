# -*- coding: utf-8 -*-
'''
Utilities to enable exception reraising across the master commands

'''

# Import python libs
import exceptions


# Import salt libs
import salt.exceptions


def raise_error(name=None, args=None, message=''):
    '''
    Raise an exception with __name__ from name, args from args
    If args is None Otherwise message from message\
    If name is empty then use "Exception"
    '''
    name = name or 'Exception'
    if hasattr(salt.exceptions, name):
        ex = getattr(salt.exceptions, name)
    elif hasattr(exceptions, name):
        ex = getattr(exceptions, name)
    else:
        name = 'SaltException'
        ex = getattr(salt.exceptions, name)
    if args is not None:
        raise ex(*args)
    else:
        raise ex(message)
