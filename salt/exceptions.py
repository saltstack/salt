'''
This module is a central location for all salt exceptions
'''

class SaltClientError(Exception):
    '''
    Problem reading the master root key
    '''
    pass


class AuthenticationError(Exception):
    '''
    If sha256 signature fails during decryption
    '''
    pass


class CommandNotFoundError(Exception):
    '''
    Used in modules or grains when a required binary is not available
    '''
    pass

class LoaderError(Exception):
    '''
    Problems loading the right renderer
    '''
    pass

class MinionError(Exception):
    '''
    Minion problems reading uris such as salt:// or http://
    '''
    pass
