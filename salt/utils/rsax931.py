# -*- coding: utf-8 -*-
'''
Create and verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
'''

# python libs
from __future__ import absolute_import
import glob
import sys
import os

# salt libs
import salt.utils

# 3rd-party libs
from ctypes import cdll, c_char_p, c_int, c_void_p, pointer, create_string_buffer
from ctypes.util import find_library

# Constants taken from openssl-1.1.0c/include/openssl/crypto.h
OPENSSL_INIT_ADD_ALL_CIPHERS = 0x00000004
OPENSSL_INIT_ADD_ALL_DIGESTS = 0x00000008
OPENSSL_INIT_NO_LOAD_CONFIG = 0x00000080


def _load_libcrypto():
    '''
    Load OpenSSL libcrypto
    '''
    if sys.platform.startswith('win'):
        return cdll.LoadLibrary('libeay32')
    elif getattr(sys, 'frozen', False) and salt.utils.is_smartos():
        return cdll.LoadLibrary(glob.glob(os.path.join(
            os.path.dirname(sys.executable),
            'libcrypto.so*'))[0])
    else:
        lib = find_library('crypto')
        if not lib and salt.utils.is_sunos():
            # Solaris-like distribution that use pkgsrc have
            # libraries in a non standard location.
            # (SmartOS, OmniOS, OpenIndiana, ...)
            lib = glob.glob(os.path.join(
                '/opt/local/lib',
                'libcrypto.so*'))
            lib = lib[0] if len(lib) > 0 else None
        if lib:
            return cdll.LoadLibrary(lib)
        raise OSError('Cannot locate OpenSSL libcrypto')


def _init_libcrypto():
    '''
    Set up libcrypto argtypes and initialize the library
    '''
    libcrypto = _load_libcrypto()

    libcrypto.RSA_new.argtypes = ()
    libcrypto.RSA_new.restype = c_void_p
    libcrypto.RSA_free.argtypes = (c_void_p, )
    libcrypto.RSA_size.argtype = (c_void_p)
    libcrypto.BIO_new_mem_buf.argtypes = (c_char_p, c_int)
    libcrypto.BIO_new_mem_buf.restype = c_void_p
    libcrypto.BIO_free.argtypes = (c_void_p, )
    libcrypto.PEM_read_bio_RSAPrivateKey.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
    libcrypto.PEM_read_bio_RSAPrivateKey.restype = c_void_p
    libcrypto.PEM_read_bio_RSA_PUBKEY.argtypes = (c_void_p, c_void_p, c_void_p, c_void_p)
    libcrypto.PEM_read_bio_RSA_PUBKEY.restype = c_void_p
    libcrypto.RSA_private_encrypt.argtypes = (c_int, c_char_p, c_char_p, c_void_p, c_int)
    libcrypto.RSA_public_decrypt.argtypes = (c_int, c_char_p, c_char_p, c_void_p, c_int)

    try:
        if libcrypto.OPENSSL_init_crypto(OPENSSL_INIT_NO_LOAD_CONFIG |
                                         OPENSSL_INIT_ADD_ALL_CIPHERS |
                                         OPENSSL_INIT_ADD_ALL_DIGESTS, None) != 1:
            raise OSError("Failed to initialize OpenSSL library (OPENSSL_init_crypto failed)")
    except AttributeError:
        # Support for OpenSSL < 1.1 (OPENSSL_API_COMPAT < 0x10100000L)
        libcrypto.OPENSSL_no_config()
        libcrypto.OPENSSL_add_all_algorithms_noconf()

    return libcrypto


libcrypto = _init_libcrypto()

# openssl/rsa.h:#define RSA_X931_PADDING 5
RSA_X931_PADDING = 5


class RSAX931Signer(object):
    '''
    Create ANSI X9.31 RSA signatures using OpenSSL libcrypto
    '''
    def __init__(self, keydata):
        '''
        Init an RSAX931Signer instance

        :param str keydata: The RSA private key in PEM format
        '''
        keydata = salt.utils.to_bytes(keydata, 'ascii')
        self._bio = libcrypto.BIO_new_mem_buf(keydata, len(keydata))
        self._rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSAPrivateKey(self._bio, pointer(self._rsa), None, None):
            raise ValueError('invalid RSA private key')

    def __del__(self):
        libcrypto.BIO_free(self._bio)
        libcrypto.RSA_free(self._rsa)

    def sign(self, msg):
        '''
        Sign a message (digest) using the private key

        :param str msg: The message (digest) to sign
        :rtype: str
        :return: The signature, or an empty string if the encryption failed
        '''
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self._rsa))
        msg = salt.utils.to_bytes(msg)
        size = libcrypto.RSA_private_encrypt(len(msg), msg, buf, self._rsa, RSA_X931_PADDING)
        if size < 0:
            raise ValueError('Unable to encrypt message')
        return buf[0:size]


class RSAX931Verifier(object):
    '''
    Verify ANSI X9.31 RSA signatures using OpenSSL libcrypto
    '''
    def __init__(self, pubdata):
        '''
        Init an RSAX931Verifier instance

        :param str pubdata: The RSA public key in PEM format
        '''
        pubdata = salt.utils.to_bytes(pubdata, 'ascii')
        pubdata = pubdata.replace('RSA ', '')
        self._bio = libcrypto.BIO_new_mem_buf(pubdata, len(pubdata))
        self._rsa = c_void_p(libcrypto.RSA_new())
        if not libcrypto.PEM_read_bio_RSA_PUBKEY(self._bio, pointer(self._rsa), None, None):
            raise ValueError('invalid RSA public key')

    def __del__(self):
        libcrypto.BIO_free(self._bio)
        libcrypto.RSA_free(self._rsa)

    def verify(self, signed):
        '''
        Recover the message (digest) from the signature using the public key

        :param str signed: The signature created with the private key
        :rtype: str
        :return: The message (digest) recovered from the signature, or an empty
            string if the decryption failed
        '''
        # Allocate a buffer large enough for the signature. Freed by ctypes.
        buf = create_string_buffer(libcrypto.RSA_size(self._rsa))
        signed = salt.utils.to_bytes(signed)
        size = libcrypto.RSA_public_decrypt(len(signed), signed, buf, self._rsa, RSA_X931_PADDING)
        if size < 0:
            raise ValueError('Unable to decrypt message')
        return buf[0:size]
