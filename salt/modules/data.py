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
    serial = salt.payload.Serial(__opts__)
    return serial.load(open(fn_, "r"))

def dump(new_data):
    '''
    Replace the entire datastore with a passed data structure

    CLI Example::

        salt '*' data.dump '{'eggs': 'spam'}' 
    '''
    if not isinstance(new_data, dict):
        if isinstance(eval(new_data, dict)):
            new_data = eval(new_data)
        else:
            return False
    fn_ = open(os.path.join(__opts__['cachedir'], 'datastore'), "w")
    serial = salt.payload.Serial(__opts__)
    serial.dump(new_data, fn_)
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

def get_value(key):
    '''
    Get a value from the minion datastore

    CLI Example::
        
        salt '*' data.get_value <key>
    
    '''
    store = load()
    return store[key]
