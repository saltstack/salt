'''
Support for Eix

'''

import salt.utils

def __virtual__():
    '''
    Only work on Gentoo systems with eix installed
    '''
    if __grains__['os'] == 'Gentoo' and salt.utils.which('eix'):
        return 'eix'
    return False


