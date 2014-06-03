# -*- coding: utf-8 -*-
'''
Manage encryption with the pynacl bindings to libsodium

The keydata consists of the following:

    priv: <HEX private keys>
    pub: <HEX public key>
    sign: <HEX signing key>
    verify: <HEX verify key>
'''

SEC_BACKEND = 'pynacl'

# Import table libs
import salt.transport.table

# Import Cyptographic libs
import nacl.public
import nacl.signing
import nacl.encoding

# Import python libs
import time


class Key(object):
    '''
    Used to manage high level nacl operations
    '''
    def __init__(self, keydata=None, **kwargs):
        self.kwargs = kwargs
        self.__generate(keydata)

    def __generate(self, keydata):
        '''
        Build the key objects, if the keydata is present load the objects from
        said keys, otherwise generate a full set of keys
        '''
        if keydata:
            if 'priv' in keydata:
                self.priv = nacl.public.PrivateKey(
                        keydata['priv'],
                        nacl.encoding.HexEncoder)
                self.pub = self.priv.public_key
            elif 'pub' in keydata:
                self.pub = nacl.public.PublicKey(
                        keydata['pub'],
                        nacl.encoding.HexEncoder)
            else:
                self.priv = nacl.public.PrivateKey.generate()
                self.pub = self.priv.public_key
            if 'sign' in keydata:
                self.sign_key = nacl.signing.SigningKey(
                        keydata['sign'],
                        nacl.encoding.HexEncoder)
                self.verify_key = self.sign_key.verify_key
            elif 'verify' in keydata:
                self.verify_key = nacl.signing.VerifyKey(
                        keydata['verify'],
                        nacl.encoding.HexEncoder)
            self.keydata = keydata
        else:
            self.keydata = {}
            self.priv = nacl.public.PrivateKey.generate()
            self.keydata['priv'] = self.priv.encode(nacl.encoding.HexEncoder)
            self.pub = self.priv.public_key
            self.keydata['pub'] = self.pub.encode(nacl.encoding.HexEncoder)
            self.sign_key = nacl.signing.SigningKey.generate()
            self.keydata['sign'] = self.sign_key.encode(nacl.encoding.HexEncoder)
            self.verify_key = self.sign_key.verify_key
            self.keydata['verify'] = self.verify_key.encode(nacl.encoding.HexEncoder)
            self.keydata['ctime'] = salt.transport.table.now()

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

    def encrypt(self, pub, msg):
        '''
        Encrypt the message intended for the owner of the passed in pubic key
        '''
        box = nacl.public.Box(self.priv, pub._key.pub)
        nonce = self._safe_nonce()
        return box.encrypt(msg, nonce)

    def decrypt(self, pub, msg):
        '''
        Decrypt a message from the given pub intended for this private key
        '''
        box = nacl.public.Box(self.priv, pub._key.pub)
        return box.decrypt(msg)

    def sign(self, msg):
        '''
        Sign the message
        '''
        return self.sign_key.sign(msg)

    def signature(self, msg):
        '''
        Return only the signature string resulting from signing the message
        '''
        return self.sign(msg).signature

    def verify(self, msg):
        '''
        Verify the message
        '''
        try:
            return self.verify_key.verify(msg)
        except nacl.signing.BadSignatureError:
            return False
