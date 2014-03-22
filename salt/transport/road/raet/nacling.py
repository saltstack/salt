# -*- coding: utf-8 -*-
'''
nacling.py raet protocol nacl (crypto) management classes
'''

# Import python libs
import time

# Import Cryptographic libs
import nacl.public
import nacl.signing
import nacl.encoding
import nacl.utils

from ioflo.base.consoling import getConsole
console = getConsole()


class Signer(object):
    '''
    Used to sign messages with nacl digital signature
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.signing.SigningKey):
                if len(key) == 32:
                    key = nacl.signing.SigningKey(key, nacl.encoding.RawEncoder)
                else:
                    key = nacl.signing.SigningKey(key, nacl.encoding.HexEncoder)
        else:
            key = nacl.signing.SigningKey.generate()
        self.key = key
        self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        self.keyraw = self.key.encode(nacl.encoding.RawEncoder)
        self.verhex = self.key.verify_key.encode(nacl.encoding.HexEncoder)
        self.verraw = self.key.verify_key.encode(nacl.encoding.RawEncoder)

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
                if len(key) == 32:
                    key = nacl.signing.VerifyKey(key, nacl.encoding.RawEncoder)
                else:
                    key = nacl.signing.VerifyKey(key, nacl.encoding.HexEncoder)
        self.key = key
        if isinstance(self.key, nacl.signing.VerifyKey):
            self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
            self.keyraw = self.key.encode(nacl.encoding.RawEncoder)
        else:
            self.keyhex = ''
            self.keyraw = ''

    def verify(self, signature, msg):
        '''
        Verify the message
        '''
        if not self.key:
            return False
        try:
            self.key.verify(signature + msg)
        except nacl.exceptions.BadSignatureError:
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
                if len(key) == 32:
                    key = nacl.public.PublicKey(key, nacl.encoding.RawEncoder)
                else:
                    key = nacl.public.PublicKey(key, nacl.encoding.HexEncoder)
        self.key = key
        if isinstance(self.key, nacl.public.PublicKey):
            self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
            self.keyraw = self.key.encode(nacl.encoding.RawEncoder)
        else:
            self.keyhex = ''
            self.keyraw = ''


class Privateer(object):
    '''
    Container for local nacl key pair
        .key is the private key
    '''
    def __init__(self, key=None):
        if key:
            if not isinstance(key, nacl.public.PrivateKey):
                if len(key) == 32:
                    key = nacl.public.PrivateKey(key, nacl.encoding.RawEncoder)
                else:
                    key = nacl.public.PrivateKey(key, nacl.encoding.HexEncoder)
        else:
            key = nacl.public.PrivateKey.generate()
        self.key = key
        self.keyhex = self.key.encode(nacl.encoding.HexEncoder)
        self.keyraw = self.key.encode(nacl.encoding.RawEncoder)
        self.pubhex = self.key.public_key.encode(nacl.encoding.HexEncoder)
        self.pubraw = self.key.public_key.encode(nacl.encoding.RawEncoder)

    def nonce(self):
        '''
        Generate a safe nonce value (safe assuming only this method is used to
        create nonce values)
        '''
        now = str(time.time() * 1000000)
        nonce = '{0}{1}'.format(
                        nacl.utils.random(nacl.public.Box.NONCE_SIZE - len(now)),
                        now)
        return nonce

    def encrypt(self, msg, pubkey, enhex=False):
        '''
        Return duple of (cyphertext, nonce) resulting from encrypting the message
        using shared key generated from the .key and the pubkey
        If pubkey is hex encoded it is converted first

        Intended for the owner of the passed in public key

        msg is string
        pub is Publican instance
        '''
        if not isinstance(pubkey, nacl.public.PublicKey):
            if len(pubkey) == 32:
                pubkey = nacl.public.PublicKey(pubkey, nacl.encoding.RawEncoder)
            else:
                pubkey = nacl.public.PublicKey(pubkey, nacl.encoding.HexEncoder)
        box = nacl.public.Box(self.key, pubkey)
        nonce = self.nonce()
        encoder = nacl.encoding.HexEncoder if enhex else nacl.encoding.RawEncoder
        encrypted = box.encrypt(msg, nonce, encoder)
        return (encrypted.ciphertext, encrypted.nonce)

    def decrypt(self, cipher, nonce, pubkey, dehex=False):
        '''
        Return decrypted msg contained in cypher using nonce and shared key
        generated from .key and pubkey.
        If pubkey is hex encoded it is converted first

        Intended for the owner of .key

        cypher is string
        nonce is string
        pub is Publican instance
        '''
        if not isinstance(pubkey, nacl.public.PublicKey):
            if len(pubkey) == 32:
                pubkey = nacl.public.PublicKey(pubkey, nacl.encoding.RawEncoder)
            else:
                pubkey = nacl.public.PublicKey(pubkey, nacl.encoding.HexEncoder)
        box = nacl.public.Box(self.key, pubkey)
        decoder = nacl.encoding.HexEncoder if dehex else nacl.encoding.RawEncoder
        return box.decrypt(cipher, nonce, decoder)
