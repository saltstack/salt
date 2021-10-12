"""
Manage a local persistent data structure that can hold any arbitrary data
specific to the minion
"""

import ast
import logging
import os

import salt.payload
import salt.utils.files

log = logging.getLogger(__name__)


def clear():
    """
    Clear out all of the data in the minion datastore, this function is
    destructive!

    CLI Example:

    .. code-block:: bash

        salt '*' data.clear
    """
    try:
        os.remove(os.path.join(__opts__["cachedir"], "datastore"))
    except OSError:
        pass
    return True


def load():
    """
    Return all of the data in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.load
    """
    try:
        datastore_path = os.path.join(__opts__["cachedir"], "datastore")
        with salt.utils.files.fopen(datastore_path, "rb") as rfh:
            return salt.payload.loads(rfh.read())
    except (OSError, NameError):
        return {}


def dump(new_data):
    """
    Replace the entire datastore with a passed data structure

    CLI Example:

    .. code-block:: bash

        salt '*' data.dump '{'eggs': 'spam'}'
    """
    if not isinstance(new_data, dict):
        if isinstance(ast.literal_eval(new_data), dict):
            new_data = ast.literal_eval(new_data)
        else:
            return False

    try:
        datastore_path = os.path.join(__opts__["cachedir"], "datastore")
        with salt.utils.files.fopen(datastore_path, "w+b") as fn_:
            salt.payload.dump(new_data, fn_)

        return True

    except (OSError, NameError):
        return False


def update(key, value):
    """
    Update a key with a value in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.update <key> <value>
    """
    store = load()
    store[key] = value
    dump(store)
    return True


def cas(key, value, old_value):
    """
    Check and set a value in the minion datastore

    CLI Example:

    .. code-block:: bash

        salt '*' data.cas <key> <value> <old_value>
    """
    store = load()
    if key not in store:
        return False

    if store[key] != old_value:
        return False

    store[key] = value
    dump(store)
    return True


def pop(key, default=None):
    """
    Pop (return & delete) a value from the minion datastore

    .. versionadded:: 2015.5.2

    CLI Example:

    .. code-block:: bash

        salt '*' data.pop <key> "there was no val"
    """
    store = load()
    val = store.pop(key, default)
    dump(store)
    return val


def get(key, default=None):
    """
    Get a (list of) value(s) from the minion datastore

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' data.get key
        salt '*' data.get '["key1", "key2"]'
    """
    store = load()

    if isinstance(key, str):
        return store.get(key, default)
    elif default is None:
        return [store[k] for k in key if k in store]
    else:
        return [store.get(k, default) for k in key]


def keys():
    """
    Get all keys from the minion datastore

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' data.keys
    """
    store = load()
    return store.keys()


def values():
    """
    Get values from the minion datastore

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' data.values
    """
    store = load()
    return store.values()


def items():
    """
    Get items from the minion datastore

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' data.items
    """
    store = load()
    return store.items()


def has_key(key):
    """
    Check if key is in the minion datastore

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' data.has_key <mykey>
    """
    store = load()
    return key in store
