# -*- coding: utf-8 -*-
'''
This handshake is based on the curvecp handshake, btu it modified to function
with the UDP/TCP RAET. This modification revolves primarily around the fact
that RAET has a more flexible header and cleartext idenity tracking is
simplified.

This handshake only supports the pynacl backend

'''

# Import table libs
import table


class Curve(object):
    '''
    The main class containing the basic routines fo the curve handshake
    '''
    def __init__(self, local, remote):
        '''
        Pass in a public key
        '''
        self.local = local
        self.remote = remote
        self.local_prime = table.Public()
        self.stage = 'new'

    def make_hello(self):
        '''
        Create a hello message
        '''
        ret = {}
        ret['C`'] = self.local_prime.keydata['pub']
        ret['box'] = self.local_prime.encrypt(self.remote, '0')
        return ret

    def verify_hello(self, hello):
        '''
        Verify hello packet
        '''
        if 'C`' not in hello or 'pub' not in hello:
            return False
        self.local_prime.decrypt(self.remote, hello['box'])
        self.remote_prime = table.Public({'pub': hello['C`']})
        self.stage = 'remote_prime'
        return True

    def make_cookie(self):
        '''
        Make the cookie
        '''
