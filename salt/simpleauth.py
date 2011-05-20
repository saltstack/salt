'''
The simpleauth module allows for a standalone authentication session to be
opened against the master. This means that the minion can communicate freely
with the master once the minion's public key has been accepted.
'''

# Import Python libs
import sys

# Import salt libs
import salt.crypt

class SAuth(object):
    '''
    Set up an object to maintain the standalone authentication session with
    the salt master
    '''
    def __init__(self, opts):
        self.opts = opts
        self.crypticle = self.__authenticate()

    def authenticate(self):
        '''
        Authenticate with the master, this method breaks the functional
        pardigmn, it will update the master information from a fresh sign in,
        signing in can occur as often as needed to keep up with the revolving
        master aes key.
        '''
        auth = salt.crypt.Auth(self.opts)
        creds = auth.sign_in()
        if creds == 'retry':
            print 'Failed to authenticate with the master, verify that this'\
                + ' minion\'s public key has been accepted on the salt master'
            sys.exit(2)
        return salt.crypt.Crypticle(creds['aes'])
