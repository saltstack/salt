# -*- coding: utf-8 -*-
'''
table backend for aes using pycrypto
'''

# Import pycrypto libs
from Crypto.Cipher import AES

# Import python libs
import hashlib
import hmac
import os


class Key(object):
    '''
    Authenticated encryption class

    Encryption algorithm: AES-CBC
    Signing algorithm: HMAC-SHA256
    '''

    AES_BLOCK_SIZE = 16
    SIG_SIZE = hashlib.sha256().digest_size

    def __init__(self, key=None, size=128, **kwargs):
        self.kwargs = kwargs
        if key is None:
            key = self.generate_key_string(size)
        self.keys = self.extract_keys(key, size)
        self.key_size = size

    @classmethod
    def generate_key_string(cls, key_size=128):
        key = os.urandom(key_size // 8 + cls.SIG_SIZE)
        return key.encode('base64').replace('\n', '')

    @classmethod
    def extract_keys(cls, key_string, key_size):
        key = key_string.decode('base64')
        assert len(key) == key_size / 8 + cls.SIG_SIZE, 'invalid key'
        return key[:-cls.SIG_SIZE], key[-cls.SIG_SIZE:]

    def encrypt(self, msg):
        '''
        encrypt data with AES-CBC and sign it with HMAC-SHA256
        '''
        aes_key, hmac_key = self.keys
        pad = self.AES_BLOCK_SIZE - len(msg) % self.AES_BLOCK_SIZE
        data = msg + pad * chr(pad)
        iv_bytes = os.urandom(self.AES_BLOCK_SIZE)
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = iv_bytes + cypher.encrypt(data)
        sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
        return data + sig

    def decrypt(self, msg):
        '''
        verify HMAC-SHA256 signature and decrypt data with AES-CBC
        '''
        aes_key, hmac_key = self.keys
        sig = msg[-self.SIG_SIZE:]
        data = msg[:-self.SIG_SIZE]
        mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
        if len(mac_bytes) != len(sig):
            raise ValueError('message authentication failed')
        result = 0
        for zipped_x, zipped_y in zip(mac_bytes, sig):
            result |= ord(zipped_x) ^ ord(zipped_y)
        if result != 0:
            raise ValueError('message authentication failed')
        iv_bytes = data[:self.AES_BLOCK_SIZE]
        data = data[self.AES_BLOCK_SIZE:]
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
        return data[:-ord(data[-1])]
