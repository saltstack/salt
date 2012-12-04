'''
Wheel system wrapper for key system
'''

import salt.key

def list_all():
    '''
    List the keys under a named status
    '''
    skey = salt.key.Key(__opts__)
    return skey.all_keys()

def accept(match):
    '''
    Accept keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.accept(match)

def delete(match):
    '''
    Delete keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.delete(match)

def reject(match):
    '''
    Delete keys based on a glob match
    '''
    skey = salt.key.Key(__opts__)
    return skey.reject(match)

def key_str(match):
    '''
    Return the key strings
    '''
    skey = salt.key.Key(__opts__)
    return skey.key_str(match)

def finger(match):
    '''
    Return the matching key fingerprints
    '''
    skey = salt.key.Key(__opts__)
    return skey.finger(match)
