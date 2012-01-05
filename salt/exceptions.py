'''
This module is a central location for all salt exceptions
'''

class SaltException(Exception):
    '''
    Base exception class; all Salt-specific exceptions should subclass this
    '''
    pass

class SaltClientError(SaltException):
    '''
    Problem reading the master root key
    '''
    pass

class AuthenticationError(SaltException):
    '''
    If sha256 signature fails during decryption
    '''
    pass

class CommandNotFoundError(SaltException):
    '''
    Used in modules or grains when a required binary is not available
    '''
    pass

class CommandExecutionError(SaltException):
    '''
    Used when a module runs a command which returns an error  and
    wants to show the user the output gracefully instead of dying
    '''
    pass

class LoaderError(SaltException):
    '''
    Problems loading the right renderer
    '''
    pass

class MinionError(SaltException):
    '''
    Minion problems reading uris such as salt:// or http://
    '''
    pass

class SaltInvocationError(SaltException):
    '''
    Used when the wrong number of arguments are sent to modules
    or invalid arguments are  specified  on  the  command  line
    '''
    pass

class PkgParseError(SaltException):
    '''
    Used when of the pkg modules cannot correctly parse the output from the CLI
    tool (pacman, yum, apt, aptitude, etc)
    '''
    pass
