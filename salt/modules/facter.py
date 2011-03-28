'''
Control aspects of the facter data
'''

import salt.config

def reload():
    '''
    Reload the Facter data for this minion
    '''
    __facter__ = salt.config.facter_data()
    return True

def list():
    '''
    Return the facter data

    CLI Example:
    salt '*' facter.list
    '''
    return __facter__

def item(key):
    '''
    Return a singe component of the facter data

    CLI Example:
    salt '*' facter.item operatingsystem
    '''
    if __facter__.has_key(key):
        return __facter__[key]
    return ''
