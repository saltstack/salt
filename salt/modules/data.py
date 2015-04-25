# -*- coding: utf-8 -*-
'''
Manage a local persistent data structure that can hold any arbitrary data
specific to the minion
'''
from __future__ import absolute_import

# Import python libs
import os
import ast

# Import salt libs
import salt.utils
import salt.payload


def clear():
    '''
    Clear out all of the data in the minion datastore, this function is
    destructive!

    CLI Example:

    .. code-block:: bash

        salt '*' data.clear
    '''
    try:
        os.remove(os.path.join(__opts__['cachedir'], 'datastore'))
    except (IOError, OSError):
        pass
    return True


def load():
    '''
    Return all of the data in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.load
    '''
    serial = salt.payload.Serial(__opts__)

    try:
        datastore_path = os.path.join(__opts__['cachedir'], 'datastore')
        fn_ = salt.utils.fopen(datastore_path, 'rb')
        return serial.load(fn_)
    except (IOError, OSError, NameError):
        return {}


def dump(new_data):
    '''
    Replace the entire datastore with a passed data structure

    CLI Example:

    .. code-block:: bash

        salt '*' data.dump '{'eggs': 'spam'}'
    '''
    if not isinstance(new_data, dict):
        if isinstance(ast.literal_eval(new_data), dict):
            new_data = ast.literal_eval(new_data)
        else:
            return False

    try:
        datastore_path = os.path.join(__opts__['cachedir'], 'datastore')
        with salt.utils.fopen(datastore_path, 'w+b') as fn_:
            serial = salt.payload.Serial(__opts__)
            serial.dump(new_data, fn_)

        return True

    except (IOError, OSError, NameError):
        return False


def update(key, value):
    '''
    Update a key with a value in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.update <key> <value>
    '''
    store = load()
    store[key] = value
    dump(store)
    return True


def getval(key):
    '''
    Get a value from the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.getval <key>
    '''
    store = load()
    if key in store:
        return store[key]


def getvals(*keys):
    '''
    Get values from the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.getvals <key> [<key> ...]
    '''
    store = load()
    ret = []
    for key in keys:
        if key in store:
            ret.append(store[key])
    return ret


def cas(key, value, old_value):
    '''
    Check and set a value in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.cas <key> <value> <old_value>
    '''
    store = load()
    if key not in store:
        return False

    if store[key] != old_value:
        return False

    store[key] = value
    dump(store)
    return True
