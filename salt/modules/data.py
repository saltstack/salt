'''
Manage a local persistent data structure that can hold any arbitrary data
specific to the minion
'''

import os
import salt.payload
import ast

def clear():
    '''
    Clear out all of the data in the minion datastore, this function is
    destructive!

    CLI Example::

        salt '*' data.clear
    '''
    try:
        os.remove(os.path.join(__opts__['cachedir'], 'datastore'))
    except IOError:
        pass
    return True

def load():
    '''
    Return all of the data in the minion datastore

    CLI Example::

        salt '*' data.load
    '''
    serial = salt.payload.Serial(__opts__)

    try:
        fn_ = open(os.path.join(__opts__['cachedir'], 'datastore'), "r")
        return serial.load(fn_)
    except (IOError, OSError):
        return {}

def dump(new_data):
    '''
    Replace the entire datastore with a passed data structure

    CLI Example::

        salt '*' data.dump '{'eggs': 'spam'}'
    '''
    if not isinstance(new_data, dict):
        if isinstance(ast.literal_eval(new_data), dict):
            new_data = ast.literal_eval(new_data)
        else:
            return False

    try:
        with open(os.path.join(__opts__['cachedir'], 'datastore'), "w") as fn_:
            serial = salt.payload.Serial(__opts__)
            serial.dump(new_data, fn_)

        return True

    except (IOError, OSError):
        return False

def update(key, value):
    '''
    Update a key with a value in the minion datastore

    CLI Example::

        salt '*' data.update <key> <value>
    '''
    store = load()
    store[key] = value
    dump(store)
    return True

def getval(key):
    '''
    Get a value from the minion datastore

    CLI Example::

        salt '*' data.getval <key>
    '''
    store = load()
    return store[key]

def getvals(keys):
    '''
    Get values from the minion datastore

    CLI Example::

        salt '*' data.getvals <key>
    '''
    store = load()
    ret = []
    for key in keys:
        if key in store:
            ret.append(store[key])
    return ret
