# -*- coding: utf-8 -*-
'''
pynacl secret key encryption
'''
# Import python libs
import time

# Import cryptographic libs
import nacl.secret
import nacl.utils


class Key(object):
    '''
    Maintain a salsa20 key
    '''
    def __init__(self, key=None, size=None, **kwargs):
        if key is None:
            if size is None or size < 32:
                size = nacl.secret.SecretBox.KEY_SIZE
            key = nacl.utils.random(size)
        if len(key) < 32:
            raise ValueError('Keysize is too small')
        self.key = key
        self.box = nacl.secret.SecretBox(key)

    def _safe_nonce(self):
        '''
        Generate a safe nonce value (safe assuming only this method is used to
        create nonce values)
        '''
        now = str(time.time() * 1000000)
        nonce = '{0}{1}'.format(
                nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE - len(now)),
                now)
        return nonce

    def encrypt(self, msg):
        '''
        Using the given key, encrypt a message
        '''
        nonce = self._safe_nonce()
        return self.box.encrypt(msg, nonce)

    def decrypt(self, msg):
        '''
        Using the given key, decrypt a message
        '''
        return self.box.decrypt(msg)
