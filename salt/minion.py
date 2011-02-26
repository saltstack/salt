'''
Routines to set up a minion
'''
# Import python libs
import os
# Import salt libs
import salt.crypt
import salt.utils

class Minion(object):
    '''
    This class instanciates a minion, runs connections for a minion, and loads
    all of the functions into the minion
    '''
    def __init__(self, opts):
        '''
        Pass in the options dict
        '''
        self.opts = opts

    def authenticate(self):
        '''
        Authenticate with the master
        '''
        pass
