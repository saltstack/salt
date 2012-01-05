'''
Manage a local persistent data structure that can hold any arbitrairy data
specific to the minion
'''

import os

import salt.payload

def load():
    '''
    Return all of the data in the minion datastore

    CLI Example::

        salt '*' data.load
    '''
    fn_ = os.path.join(__opts__['cachedir'], 'datastore')
    if not os.path.isfile(fn_):
        return {}
    serial = Serial(__opts__)
    return serial.load(fn_)

def dump(new_data):
    '''
    Replace the entire datastore with a passed data structure

    CLI Example::

        salt '*' data.dump '{'eggs': 'spam'}' 
    '''
    if not isinstance(new_data, dict):
        return False
    fn_ = os.path.join(__opts__['cachedir'], 'datastore')
    serial = Serial(__opts__)
    serial.dump(new_data)
    return True

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
