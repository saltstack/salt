# -*- coding: utf-8 -*-
'''
Support for getting and setting the environment variables
of the current salt process.
'''

# Import python libs
import os
import logging

# Import salt libs
from salt._compat import string_types
from salt.exceptions import SaltException

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'environ'

def __virtual__():
    '''
    No dependency checks, so just return the __virtualname__
    '''
    return __virtualname__


def set(environ):
    '''
    Set the salt process environment variables.

    Accepts a dict 'environ'. Each top-level key of the dict
    are the names of the environment variables to set.
    The value to set must be a string.


    CLI Example:

    .. code-block:: bash

        salt '*' environ.set '{"foo": "bar", "baz": "quux"}'
    '''
    ret = {}
    if not isinstance(environ, dict):
        raise SaltException('The "environ" argument variable must be a dict')
    try:
        for k, v in environ.items():
            if not isinstance(v, string_types):
                raise SaltException('The value of "environ" keys must be string type')
            os.environ[k] = v
            ret[k] = os.environ[k]
    except Exception as e:
        raise SaltException(e)
    return ret

def get(keys):
    '''
    Get the salt process environment variables.

    'keys' can be either a string or a list of strings that will
    be used as the keys for environment lookup.

    CLI Example:

    .. code-block:: bash

        salt '*' environ.get foo
        salt '*' environ.get '[foo, baz]'
    '''
    ret = {}
    key_list = []
    if isinstance(keys, string_types):
        key_list.append(keys)
    elif isinstance(keys, list):
        key_list = keys
    else:
        raise SaltException('The "keys" argument variable must be string or list.')
    for key in key_list:
        ret[key] = os.environ[key]
    return ret

def get_all():
    '''
    Return a dict of the entire environment set for the salt process
    '''
    return dict(os.environ)

