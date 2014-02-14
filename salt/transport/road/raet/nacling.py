# -*- coding: utf-8 -*-
'''
nacling.py raet protocol nacl (crypto) management classes
'''

# Import python libs
import time

# Import Cyptographic libs
import nacl.public
import nacl.signing
import nacl.encoding
import nacl.utils
import nacl.secret

from ioflo.base.consoling import getConsole
console = getConsole()


class Signer(object):
    '''
    Used to sign messages with nacl digital signature
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.signing.SigningKey):
                key = nacl.signing.SigningKey(key, nacl.encoding.HexEncoder)
        else:
            key = nacl.signing.SigningKey.generate()
        self.key = key
        self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        self.verhex = self.key.verify_key.encode(nacl.encoding.HexEncoder)

    def sign(self, msg):
        '''
        Sign the message
        '''
        return self.key.sign(msg)

    def signature(self, msg):
        '''
        Return only the signature string resulting from signing the message
        '''
        return self.key.sign(msg).signature


class Verifier(object):
    '''
    Used to verify messages with nacl digital signature
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.signing.VerifyKey):
                key = nacl.signing.VerifyKey(key, nacl.encoding.HexEncoder)
        self.key = key
        if isinstance(self.key, nacl.signing.VerifyKey):
            self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        else:
            self.keyhex = ''

    def verify(self, signature, msg):
        '''
        Verify the message
        '''
        if not self.key:
            return False
        try:
            self.key.verify(signature + msg)
        except nacl.signing.BadSignatureError:
            return False
        return True


class Publican(object):
    '''
    Container to manage remote nacl public key
        .key is the public key
    Intelligently converts hex encoded to object
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.public.PublicKey):
                key = nacl.public.PublicKey(key, nacl.encoding.HexEncoder)
        self.key = key
        if isinstance(self.key, nacl.public.PublicKey):
            self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        else:
            self.keyhex = ''


class Privateer(object):
    '''
    Container for local nacl key pair
        .key is the private key
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.public.PrivateKey):
                key = nacl.public.PrivateKey(key, nacl.encoding.HexEncoder)
        else:
            key = nacl.public.PrivateKey.generate()
        self.key = key
        self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        self.pubhex = self.key.public_key.encode(nacl.encoding.HexEncoder)

    def _nonce(self):
        '''
        Generate a safe nonce value (safe assuming only this method is used to
        create nonce values)
        '''
        now = str(time.time() * 1000000)
        nonce = '{0}{1}'.format(
                nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE - len(now)),
                now)
        return nonce

    def encrypt(self, msg, pub):
        '''
        Return duple of (cyphertext, nonce) resulting from encrypting the message
        using shared key generated from the .key and the pub.key

        Intended for the owner of the passed in public key

        msg is string
        pub is Publican instance
        '''
        box = nacl.public.Box(self.key, pub.key)
        nonce = self._nonce()
        encrypted = box.encrypt(msg, nonce)
        return (encrypted.ciphertext, encrypted.nonce)

    def decrypt(self, cipher, nonce, pub):
        '''
        Return decripted msg contained in cypher using nonce and shared key
        generated from .key and pub.key.

        Intented for the owner of .key

        cypher is string
        nonce is string
        pub is Publican instance
        '''
        box = nacl.public.Box(self.key, pub.key)
        return box.decrypt(cipher, nonce)
