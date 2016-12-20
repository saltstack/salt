# -*- coding: utf-8 -*-
'''
Data cache plugin for Consul key/value data store.
This requires python-consul python package.

.. versionadded:: 2016.11.2
'''
from __future__ import absolute_import
import logging
try:
    import consul
    HAS_CONSUL = True
except ImportError:
    HAS_CONSUL = False

from salt.exceptions import SaltCacheError

log = logging.getLogger(__name__)
CONSUL = None


# Define the module's virtual name
__virtualname__ = 'consul'


def __virtual__():
    '''
    Confirm this python-consul package is installed
    '''
    if not HAS_CONSUL:
        return (False, "Please install python-consul package to use consul data cache driver")

    global CONSUL
    CONSUL = consul.Consul()

    return __virtualname__


def store(bank, key, data):
    '''
    Store a key value.
    '''
    c_key = '{0}/{1}'.format(bank, key)
    try:
        c_data = __context__['serial'].dumps(data)
        CONSUL.kv.put(c_key, c_data)
    except Exception as exc:
        raise SaltCacheError(
            'There was an error writing the key, {0}: {1}'.format(
                c_key, exc
            )
        )


def fetch(bank, key):
    '''
    Fetch a key value.
    '''
    c_key = '{0}/{1}'.format(bank, key)
    try:
        _, value = CONSUL.kv.get(c_key)
        if value is None:
            return value
        return __context__['serial'].loads(value['Value'])
    except Exception as exc:
        raise SaltCacheError(
            'There was an error reading the key, {0}: {1}'.format(
                c_key, exc
            )
        )


def flush(bank, key=None):
    '''
    Remove the key from the cache bank with all the key content.
    '''
    if key is None:
        c_key = bank
    else:
        c_key = '{0}/{1}'.format(bank, key)
    try:
        return CONSUL.kv.delete(c_key, recurse=key is None)
    except Exception as exc:
        raise SaltCacheError(
            'There was an error removing the key, {0}: {1}'.format(
                c_key, exc
            )
        )


def list(bank):
    '''
    Return an iterable object containing all entries stored in the specified bank.
    '''
    try:
        _, keys = CONSUL.kv.get(bank + '/', keys=True, separator='/')
    except Exception as exc:
        raise SaltCacheError(
            'There was an error getting the key "{0}": {1}'.format(
                bank, exc
            )
        )
    if keys is None:
        keys = []
    else:
        # Any key could be a branch and a leaf at the same time in Consul
        # so we have to return a list of unique names only.
        out = set()
        for key in keys:
            out.add(key[len(bank) + 1:].rstrip('/'))
        keys = list(out)
    return keys


def contains(bank, key):
    '''
    Checks if the specified bank contains the specified key.
    '''
    if key is None:
        return True  # any key could be a branch and a leaf at the same time in Consul
    else:
        try:
            c_key = '{0}/{1}'.format(bank, key)
            _, value = CONSUL.kv.get(c_key)
        except Exception as exc:
            raise SaltCacheError(
                'There was an error getting the key, {0}: {1}'.format(
                    c_key, exc
                )
            )
        return value is not None
